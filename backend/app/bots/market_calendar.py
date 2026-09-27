"""Market-hours awareness (PRD Section 17): bots act only inside the exchange session.

NSE/BSE equity normal session: 09:15-15:30 IST, Mon-Fri, minus exchange holidays.
Holidays change every year - load them from the official NSE circular via config/DB, don't hardcode.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


@dataclass
class ExchangeCalendar:
    name: str = "NSE"
    open_time: time = time(9, 15)
    close_time: time = time(15, 30)
    holidays: set[date] = field(default_factory=set)
    special_sessions: set[date] = field(default_factory=set)   # e.g. Muhurat / weekend special trading

    def is_trading_day(self, d: date) -> bool:
        if d in self.special_sessions:
            return True
        return d.weekday() < 5 and d not in self.holidays

    def is_open(self, when: datetime) -> bool:
        if when.tzinfo is None:
            raise ValueError("use timezone-aware datetimes")
        local = when.astimezone(IST)
        return self.is_trading_day(local.date()) and self.open_time <= local.time() < self.close_time
