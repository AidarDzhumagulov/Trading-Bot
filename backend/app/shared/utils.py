from decimal import Decimal, ROUND_DOWN


def truncate_to_precision(value: float, precision: int) -> float:
    d = Decimal(str(value))
    quantizer = Decimal('0.1') ** precision
    return float(d.quantize(quantizer, rounding=ROUND_DOWN))

def calculate_grid(
        current_price: float,
        total_budget: float,
        grid_levels: int,
        grid_length_pct: float,
        first_step_pct: float,
        volume_scale_pct: float,
        amount_precision: int = 4,
        price_precision: int = 2
):
    first_order_price = current_price * (1 - first_step_pct / 100)
    last_order_price = first_order_price * (1 - grid_length_pct / 100)

    if grid_levels <= 1:
        price_step = 0
    else:
        price_step = (first_order_price - last_order_price) / (grid_levels - 1)

    multiplier = 1 + (volume_scale_pct / 100)
    sum_weights = sum([multiplier ** i for i in range(grid_levels)])

    first_order_v_usdt = total_budget / sum_weights

    orders = []
    for i in range(grid_levels):
        order_price = first_order_price - (i * price_step)
        order_volume_usdt = first_order_v_usdt * (multiplier ** i)
        amount_base = order_volume_usdt / order_price

        orders.append({
            "index": i,
            "price": round(order_price, price_precision),
            "amount_usdt": round(order_volume_usdt, 2),
            "amount_base": truncate_to_precision(amount_base, amount_precision)
        })

    return orders