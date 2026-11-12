"""Haftalık satış tahmini (ciro ya da adet).

Ön işleme (gerekçeye dayalı, "Düzeltilmiş" seçeneği):
1. İlk (2–5 Ocak) ve son (28–31 Aralık) haftalar kısmi olduğu için seriye alınmaz.
2. 20 ve 27 Temmuz haftaları doğrusal enterpolasyonla doldurulur: 22 Temmuz – 2 Ağustos arasında
   hiç fatura yok; bu bir talep düşüşü değil, kayıt boşluğu.
3. Pandemi kısıtlamaları döneminde (16 Mart – 1 Haziran) Hampel filtresi uygulanır: 5 haftalık
   hareketli ortancadan 3 MAD'den fazla sapan hafta ortancayla değiştirilir. Bu dönemin dışındaki
   hareketlere (ör. Ekim zirvesi) dokunulmaz; gerçek talep olabilirler.

Doğrulama (veri sızıntısı olmadan):
- Son 4 hafta "son test" olarak ayrılır; model seçiminde hiç kullanılmaz, yalnızca raporlanır.
- Model seçimi kayan başlangıçlı doğrulamayla yapılır: model her başlangıç noktasına kadarki veriyle
  kurulur ve sonraki 4 haftayı tahmin eder. Ön işleme her seferinde yalnızca o eğitim penceresine
  uygulanır; doğrulama haftaları eğitim verisini etkilemez.
- %80 tahmin aralığı: kayan doğrulama hatalarının karekök ortalaması (RMSE) × 1,28 × √h.

Tahmin: seçilen model tüm seriyle yeniden kurulur. 21 Aralık'tan sonraki ilk adım kısmi 28 Aralık
haftasıdır (grafikte "köprü" olarak gösterilir, toplamlara katılmaz); ufuk 4 Ocak 2021'den başlar.
"""

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from src.config import PANDEMIC_BAND, SALES_GAP_WEEKS

MODELS = ["Naive", "Doğrusal trend", "Üstel düzeltme"]
TEST_WEEKS = 4          # son test: seçimde kullanılmaz
FOLD_HORIZON = 4        # her kayan doğrulama adımında tahmin edilen hafta
FIRST_ORIGIN = 31       # ilk doğrulama başlangıcı (10 Ağustos haftası; satış boşluğundan sonra)
Z80 = 1.2816
MIN_ACTIVE_WEEKS = 40


def weekly_series(df: pd.DataFrame, value: str = "Revenue") -> pd.Series:
    """Tam haftalardan oluşan seri (6 Ocak – 21 Aralık 2020, 51 hafta)."""
    s = df.groupby("InvoiceWeek")[value].sum()
    weeks = pd.date_range("2019-12-30", "2020-12-28", freq="W-MON")
    return s.reindex(weeks, fill_value=0.0).iloc[1:-1].astype(float)


def hampel(s: pd.Series, window: int = 5, k: float = 3.0) -> tuple[pd.Series, pd.Series]:
    med = s.rolling(window, center=True, min_periods=1).median()
    mad = (s - med).abs().rolling(window, center=True, min_periods=1).median() * 1.4826
    flagged = (s - med).abs() > k * mad.replace(0, np.nan)
    return s.where(~flagged, med), flagged


def prepare(s: pd.Series, adjust: bool = True) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Ön işleme; yalnızca verilen pencerenin kendi değerlerini kullanır (sızıntı yok).
    Dönüş: (modelde kullanılacak seri, doldurulan haftalar, sınırlanan haftalar)."""
    none = pd.Series(False, index=s.index)
    if not adjust:
        return s, none, none
    clean = s.copy()
    filled = s.index.isin(pd.to_datetime(list(SALES_GAP_WEEKS)))
    filled = pd.Series(filled, index=s.index)
    clean[filled] = np.nan
    clean = clean.interpolate(limit_direction="both")
    capped_values, flagged = hampel(clean)
    in_pandemic = (s.index >= pd.Timestamp(PANDEMIC_BAND[0])) & (s.index < pd.Timestamp(PANDEMIC_BAND[1]))
    capped = flagged & in_pandemic
    clean[capped] = capped_values[capped]
    return clean, filled, capped


def _predict(model: str, train: pd.Series, h: int) -> np.ndarray:
    if model == "Naive":
        return np.repeat(train.iloc[-1], h)
    if model == "Doğrusal trend":
        t = np.arange(len(train))
        slope, intercept = np.polyfit(t, train.values, 1)
        return intercept + slope * np.arange(len(train), len(train) + h)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = ExponentialSmoothing(train.values, trend="add", damped_trend=True).fit()
    return fit.forecast(h)


def _errors(actual: np.ndarray, pred: np.ndarray) -> np.ndarray:
    return actual - pred


def _summary(err: np.ndarray, actual: np.ndarray) -> dict:
    ok = actual != 0
    return {"mae": float(np.mean(np.abs(err))), "rmse": float(np.sqrt(np.mean(err ** 2))),
            "mape": float(np.mean(np.abs(err[ok]) / actual[ok])) if ok.any() else float("nan")}


def run(s: pd.Series, horizon: int = 8, adjust: bool = True) -> dict:
    """Modelleri sızıntısız biçimde sınar, seçer ve tahmin üretir."""
    active = int((s > 0).sum())
    out = {"enough_data": active >= MIN_ACTIVE_WEEKS, "active_weeks": active, "series": s}
    if not out["enough_data"]:
        return out

    n = len(s)
    selection_end = n - TEST_WEEKS                      # son testten önceki haftalar
    origins = list(range(FIRST_ORIGIN, selection_end - FOLD_HORIZON + 1, FOLD_HORIZON))
    cv_err = {m: [] for m in MODELS}
    cv_act = []
    for o in origins:
        train, _, _ = prepare(s.iloc[:o], adjust)       # ön işleme yalnızca eğitim penceresinde
        actual = s.iloc[o:o + FOLD_HORIZON].values
        cv_act.append(actual)
        for m in MODELS:
            cv_err[m].append(_errors(actual, _predict(m, train, FOLD_HORIZON)))
    act = np.concatenate(cv_act)
    table = pd.DataFrame({m: _summary(np.concatenate(cv_err[m]), act) for m in MODELS}).T
    best = table["mape"].idxmin()

    # Son test: seçimde kullanılmayan son 4 hafta
    train, _, _ = prepare(s.iloc[:selection_end], adjust)
    test_actual = s.iloc[selection_end:].values
    test = {m: _summary(_errors(test_actual, _predict(m, train, TEST_WEEKS)), test_actual)["mape"] for m in MODELS}

    # Son model: tüm seri; ilk adım kısmi 28 Aralık haftası (köprü), sonra ufuk
    clean, filled, capped = prepare(s, adjust)
    steps = horizon + 1
    point = np.clip(_predict(best, clean, steps), 0, None)
    band = Z80 * table.loc[best, "rmse"] * np.sqrt(np.arange(1, steps + 1))
    weeks = pd.date_range(s.index[-1] + pd.Timedelta(weeks=1), periods=steps, freq="W-MON")
    frame = pd.DataFrame({"point": point, "lo": np.clip(point - band, 0, None), "hi": point + band}, index=weeks)
    forecast, bridge = frame.iloc[1:], frame.iloc[:1]
    h = np.arange(2, steps + 1)
    total_band = Z80 * table.loc[best, "rmse"] * np.sqrt(h.sum())
    out.update({
        "clean": clean, "filled": filled, "capped": capped, "table": table, "best": best, "test": test,
        "beats_naive": best != "Naive" and table.loc[best, "mape"] < table.loc["Naive", "mape"],
        "cv_start": s.index[FIRST_ORIGIN], "test_start": s.index[selection_end], "n_folds": len(origins),
        "forecast": forecast, "bridge": bridge,
        "total": float(forecast["point"].sum()), "total_lo": float(max(forecast["point"].sum() - total_band, 0)),
        "total_hi": float(forecast["point"].sum() + total_band),
    })
    last8 = s.iloc[-8:].mean()
    out["last8_mean"] = float(last8)
    out["signal"] = ("artış" if forecast["lo"].mean() > last8 else
                     "düşüş" if forecast["hi"].mean() < last8 else "belirgin değişim yok")
    return out
