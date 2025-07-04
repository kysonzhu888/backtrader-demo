class FuturesInstrumentModel:
    ContractOpenInterestQuota: float | int | None = None
    ContractTradeQuota: float | int | None = None
    CreateDate: str | None = None
    DownStopPrice: float | None = None
    ExchangeCode: str | None = None
    ExchangeID: str | None = None
    ExpireDate: str | None = None
    FloatVolume: float | None = None
    InstrumentID: str | None = None
    InstrumentName: str | None = None
    InstrumentStatus: int | None = None
    IsRecent: bool | None = None
    IsTrading: bool | None = None
    LastVolume: float | int | None = None
    LongMarginRatio: float | None = None
    MainContract: int | None = None
    OpenDate: str | None = None
    PreClose: float | None = None
    PriceTick: float | None = None
    ProductID: str | None = None
    ProductName: str | None = None
    ProductOpenInterestQuota: float | int | None = None
    ProductTradeQuota: float | int | None = None
    ProductType: str | None = None
    SettlementPrice: float | None = None
    ShortMarginRatio: float | None = None
    TotalVolume: float | int | None = None
    UniCode: str | None = None
    UpStopPrice: float | None = None
    VolumeMultiple: int | None = None

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self):
        return self.__dict__ 