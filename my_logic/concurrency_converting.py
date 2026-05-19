def convert_currency(source_currency: str, destination_currency: str, vnd_exchange_rate: dict[str, float], source_money: float) -> float:
    """
        This function is use to convert the amount of money between currencies. 
        args:
            source_currency: The currency of the source money.
            destination_currency: The currency of the destination money.
            vnd_exchange_rate: The exchange rate between currencies and VND.
            source_money: The amount of money to convert.
        returns:
            The amount of money in the destination currency.
    """
    if source_currency == destination_currency:
        return source_money
    
    if source_currency == "VND":
        return source_money / vnd_exchange_rate[destination_currency]
    
    if destination_currency == "VND":
        return source_money * vnd_exchange_rate[source_currency]

    return source_money * vnd_exchange_rate[source_currency] / vnd_exchange_rate[destination_currency]

