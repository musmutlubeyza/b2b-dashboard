"""Haftalık satış tahmini.

Adımlar:
1. Haftalık seri: ilk (2–5 Ocak) ve son (28–31 Aralık) haftalar kısmi olduğu için dışarıda bırakılır.
2. Aykırı haftalar (pandemi düşüş/sıçramaları, satış boşluğu) Hampel filtresiyle sınırlanır:
   5 haftalık hareketli ortancadan 3 MAD'den fazla sapan hafta, o ortancayla değiştirilir.
3. Üç model son 6 hafta saklanarak sınanır; en düşük MAPE'li model seçilir.
4. Seçilen model tüm seriyle yeniden kurulup ufuk kadar ileri tahmin yapar.
   %80 aralık: doğrulama hatasının karekökü ortalaması (RMSE) × 1,28 × √h (ufuk uzadıkça genişler).
   Son (kısmi) hafta modelde olmadığı için tahmin bir hafta sonrasından, 4 Ocak 2021 haftasından başlar.
"""

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

MODELS = ["Naive", "Doğrusal trend", "Üstel düzeltme"]
HOLDOUT = 6
Z80 = 1.2816
MIN_ACTIVE_WEEKS = 40


def weekly_series(df: pd.DataFrame, value: str = "Revenue") -> pd.Series:
    s = df.groupby("InvoiceWeek")[value].sum()
    weeks = pd.date_range("2019-12-30", "2020-12-28", freq="W-MON")
    return s.reindex(weeks, fill_value=0.0).iloc[1:-1].astype(float)


def cap_outliers(s: pd.Series, window: int = 5, k: float = 3.0) -> tuple[pd.Series, pd.Series]:
    med = s.rolling(window, center=True, min_periods=1).median()
    mad = (s - med).abs().rolling(window, center=True, min_periods=1).median() * 1.4826
    flagged = (s - med).abs() > k * mad.replace(0, np.nan)
    return s.where(~flagged, med), flagged


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


def run(s: pd.Series, horizon: int = 8, cap: bool = True) -> dict:
    """Modelleri sınar, en iyisini seçer ve tahmin ile aralığı döndürür."""
    active = int((s > 0).sum())
    out = {"enough_data": active >= MIN_ACTIVE_WEEKS, "active_weeks": active, "series": s}
    if not out["enough_data"]:
        return out
    clean, flagged = cap_outliers(s) if cap else (s, pd.Series(False, index=s.index))
    train, test = clean.iloc[:-HOLDOUT], s.iloc[-HOLDOUT:]
    rows = []
    for m in MODELS:
        err = test.values - _predict(m, train, HOLDOUT)
        rows.append({"model": m, "mae": float(np.mean(np.abs(err))),
                     "mape": float(np.mean(np.abs(err) / np.where(test.values == 0, np.nan, test.values))),
                     "rmse": float(np.sqrt(np.mean(err ** 2)))})
    table = pd.DataFrame(rows).set_index("model")
    best = table["mape"].idxmin()
    # Seri 21 Aralık haftasında bitiyor; kısmi 28 Aralık haftasını atlayıp 4 Ocak'tan başlıyoruz
    point = np.clip(_predict(best, clean, horizon + 1)[1:], 0, None)
    h = np.arange(2, horizon + 2)
    band = Z80 * table.loc[best, "rmse"] * np.sqrt(h)
    weeks = pd.date_range(s.index[-1] + pd.Timedelta(weeks=2), periods=horizon, freq="W-MON")
    total_band = Z80 * table.loc[best, "rmse"] * np.sqrt(h.sum())
    out.update({
        "clean": clean, "flagged": flagged, "table": table, "best": best,
        "beats_naive": best != "Naive" and table.loc[best, "mape"] < table.loc["Naive", "mape"],
        "forecast": pd.DataFrame({"point": point, "lo": np.clip(point - band, 0, None), "hi": point + band}, index=weeks),
        "total": float(point.sum()), "total_lo": float(max(point.sum() - total_band, 0)), "total_hi": float(point.sum() + total_band),
        "holdout_start": s.index[-HOLDOUT],
    })
    last8 = s.iloc[-8:].mean()
    lo_avg, hi_avg = out["forecast"]["lo"].mean(), out["forecast"]["hi"].mean()
    out["last8_mean"] = float(last8)
    out["signal"] = "artış" if lo_avg > last8 else ("düşüş" if hi_avg < last8 else "belirgin değişim yok")
    return out
