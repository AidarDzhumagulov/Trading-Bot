def calculate_grid(
        current_price: float,
        total_budget: float,
        grid_levels: int,
        grid_length_pct: float,
        first_step_pct: float,
        volume_scale_pct: float
):
    first_order_price = current_price * (1 - first_step_pct / 100)
    last_order_price = first_order_price * (1 - grid_length_pct / 100)

    price_step = (first_order_price - last_order_price) / grid_levels if grid_levels > 0 else 0

    multiplier = 1 + (volume_scale_pct / 100)
    weights = [multiplier ** i for i in range(grid_levels + 1)]
    sum_weights = sum(weights)

    first_order_v_usdt = total_budget / sum_weights

    orders = []
    for i in range(grid_levels + 1):
        order_price = first_order_price - (i * price_step)
        order_volume_usdt = first_order_v_usdt * (multiplier ** i)

        orders.append({
            "index": i,
            "price": round(order_price, 2),
            "amount_usdt": round(order_volume_usdt, 2),
            "amount_base": order_volume_usdt / order_price
        })

    return orders