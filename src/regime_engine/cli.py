import argparse
from regime_engine.loader import load_sample_data
from regime_engine.features import (
    compute_ema,
    compute_returns,
    compute_realized_vol,
)
from regime_engine.metrics import (
    compute_market_bias,
    compute_risk_level,
    compute_breakout_probability,
    compute_downside_shock_risk,
    compute_key_levels,
    compute_structural_score,
    compute_volatility_regime,
    compute_momentum_state,
    compute_liquidity_context,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the regime engine (offline).")
    parser.add_argument("--symbol", required=True, help="Asset symbol, e.g., SPY")
    args = parser.parse_args()

    df = load_sample_data(args.symbol)
    close = df["close"]

    ema_fast = compute_ema(close, 20)
    ema_slow = compute_ema(close, 100)
    returns = compute_returns(close)
    rv = compute_realized_vol(returns)

    market_bias = compute_market_bias(df, n_f=20, n_s=100, alpha=0.7, beta=0.3)
    risk_level = compute_risk_level(df, n_f=20, n_s=100, peak_window=252)

    vol_regime = compute_volatility_regime(
        df,
        rl=risk_level,
        n_f=20,
        n_s=100,
        n_sh=10,
        n_lg=50,
    )

    kl = compute_key_levels(df, n_f=20, W=250, k=3, eta=0.35, N=3, min_strength=0.35)

    # nearest resistance above and nearest support below
    L_up = kl["resistances"][0]["price"] if kl["resistances"] else None
    L_dn = kl["supports"][0]["price"] if kl["supports"] else None

    bp_up, bp_dn = compute_breakout_probability(
        df,
        mb=market_bias,
        rl=risk_level,
        n_f=20,
        atr_short_n=10,
        atr_long_n=50,
        level_lookback=50,
        L_up=L_up,
        L_dn=L_dn,
    )

    dsr = compute_downside_shock_risk(
        df,
        mb=market_bias,
        rl=risk_level,
        n_f=20,
        n_s=100,
        H=60,
        m=2.5,
    )

    ss = compute_structural_score(
        df,
        mb=market_bias,
        rl=risk_level,
        dsr=dsr,
        key_levels=kl,
        n_f=20,
        n_s=100,
        n_c=20,
    )

    momentum = compute_momentum_state(
        df,
        mb=market_bias,
        ss=ss,
        vrs=float(vol_regime["vrs"]),
        bp_up=bp_up,
        bp_dn=bp_dn,
        n_f=20,
        n_m=20,
        k_m=2.0,
        n_c=20,
    )

    liquidity = compute_liquidity_context(
        df,
        vrs=float(vol_regime["vrs"]),
        er=float(momentum["er"]),
        n_dv=20,
        h=5,
    )

    asof = df.index[-1].date().isoformat()

    result = {
        "symbol": args.symbol.upper(),
        "asof": asof,
        "key_levels": kl,
        "vol_regime": vol_regime,
        "momentum": momentum,
        "liquidity": liquidity,
        "metrics": {
            "price": float(close.iloc[-1]),
            "ema_fast": float(ema_fast.iloc[-1]),
            "ema_slow": float(ema_slow.iloc[-1]),
            "realized_vol": float(rv.iloc[-1]),
            "market_bias": float(market_bias),
            "risk_level": float(risk_level),
            "vrs": float(vol_regime["vrs"]),
            "breakout_up": float(bp_up),
            "breakout_down": float(bp_dn),
            "downside_shock_risk": float(dsr),
            "structural_score": float(ss),
            "cms": float(momentum["cms"]),
            "ii": float(momentum["ii"]),
            "lq": float(liquidity["lq"]),
        },
    }

    print(result)


if __name__ == "__main__":
    main()
