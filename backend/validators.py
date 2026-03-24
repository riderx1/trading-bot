"""Schema and config validators for external payloads and runtime safety."""


def validate_config(cfg: dict):
    required_paths = [
        ("execution", "mode"),
        ("trading", "paper_trading"),
        ("trading", "mode"),
        ("trading", "trade_size_usdc"),
        ("trading", "signal_threshold"),
        ("trading", "min_edge"),
        ("trading", "min_confidence"),
        ("trading", "signal_neutral_band_pct"),
        ("trading", "momentum_scale"),
        ("trading", "medium_signal_floor"),
        ("trading", "strong_signal_floor"),
        ("trading", "probability_floor"),
        ("trading", "probability_ceiling"),
        ("trading", "higher_timeframe_boost"),
        ("trading", "conflict_penalty"),
        ("trading", "ta_alignment_boost"),
        ("trading", "ta_conflict_penalty"),
        ("trading", "max_signal_age_seconds"),
        ("trading", "max_market_age_seconds"),
        ("trading", "trade_bucket_seconds"),
        ("trading", "cooldown_seconds"),
        ("trading", "emit_signals_only"),
        ("trading", "max_total_exposure_usdc"),
        ("trading", "max_per_market_exposure_usdc"),
        ("trading", "max_cluster_exposure_usdc"),
        ("trading", "slippage_bps"),
        ("trading", "max_spread_bps"),
        ("trading", "min_liquidity"),
        ("trading", "min_hours_to_resolution"),
        ("binance", "signal_intervals"),
    ]
    for section, key in required_paths:
        if section not in cfg or key not in cfg[section]:
            raise ValueError(f"Missing required config: {section}.{key}")

    if cfg["trading"]["mode"] not in {"arbitrage", "signal", "both"}:
        raise ValueError("Invalid trading.mode")

    execution_mode = str(
        cfg.get("execution_mode", cfg.get("execution", {}).get("mode", "paper"))
    ).strip().lower()
    if execution_mode != "paper":
        raise ValueError("execution_mode must be 'paper'")

    if str(cfg["execution"]["mode"]).strip().lower() != "paper":
        raise ValueError("execution.mode must be 'paper'")

    if not isinstance(cfg["binance"]["signal_intervals"], list) or not cfg["binance"]["signal_intervals"]:
        raise ValueError("binance.signal_intervals must be a non-empty list")

    positive_numbers = [
        "trade_size_usdc",
        "signal_threshold",
        "min_edge",
        "min_confidence",
        "signal_neutral_band_pct",
        "momentum_scale",
        "medium_signal_floor",
        "strong_signal_floor",
        "probability_floor",
        "probability_ceiling",
        "higher_timeframe_boost",
        "conflict_penalty",
        "ta_alignment_boost",
        "ta_conflict_penalty",
        "max_signal_age_seconds",
        "max_market_age_seconds",
        "trade_bucket_seconds",
        "cooldown_seconds",
        "max_total_exposure_usdc",
        "max_per_market_exposure_usdc",
        "max_cluster_exposure_usdc",
        "max_spread_bps",
        "min_liquidity",
        "min_hours_to_resolution",
    ]
    for field in positive_numbers:
        if float(cfg["trading"][field]) <= 0:
            raise ValueError(f"trading.{field} must be > 0")

    if float(cfg["trading"]["probability_ceiling"]) <= float(
        cfg["trading"]["probability_floor"]
    ):
        raise ValueError("trading.probability_ceiling must be > probability_floor")

    if float(cfg["trading"]["strong_signal_floor"]) < float(
        cfg["trading"]["medium_signal_floor"]
    ):
        raise ValueError("trading.strong_signal_floor must be >= medium_signal_floor")

    if not isinstance(cfg["trading"]["emit_signals_only"], bool):
        raise ValueError("trading.emit_signals_only must be true or false")

    hyperliquid_cfg = cfg.get("hyperliquid", {}) if isinstance(cfg, dict) else {}
    if not isinstance(hyperliquid_cfg.get("symbols", []), list) or not hyperliquid_cfg.get("symbols"):
        raise ValueError("hyperliquid.symbols must be a non-empty list")


def validate_binance_price_payload(payload: dict):
    if not isinstance(payload, dict) or "price" not in payload:
        raise ValueError("Invalid Binance price payload")
    float(payload["price"])


def validate_binance_klines_payload(payload: list):
    if not isinstance(payload, list) or not payload:
        raise ValueError("Invalid Binance klines payload")
    for row in payload:
        if not isinstance(row, list) or len(row) < 6:
            raise ValueError("Invalid Binance kline row")
        float(row[1])
        float(row[2])
        float(row[3])
        float(row[4])
        float(row[5])


def validate_polymarket_market_item(item: dict):
    """Backward-compatible validator stub for legacy market payloads.

    Polymarket feed is deprecated, but this validator remains to keep legacy
    import paths and optional code branches safe during migration.
    """
    if not isinstance(item, dict):
        raise ValueError("Invalid market item")
