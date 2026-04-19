from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EuropeanCountryDialCode:
    iso_code: str
    country_name: str
    dial_code: str

    @property
    def flag_emoji(self) -> str:
        if len(self.iso_code) != 2 or not self.iso_code.isalpha():
            return "🏳️"
        base = 127397
        return "".join(chr(base + ord(char)) for char in self.iso_code.upper())

    @property
    def display_label(self) -> str:
        return f"{self.flag_emoji} {self.country_name} ({self.dial_code})"


# Europa-Definition für Profilmanager:
# Souveräne Staaten in geografischem Europa inkl. transkontinentaler Staaten mit
# erheblichem europäischem Bezug (z. B. Türkei, Russland, Georgien etc.) sowie Kosovo.
EUROPEAN_COUNTRY_DIAL_CODES: tuple[EuropeanCountryDialCode, ...] = (
    EuropeanCountryDialCode("AL", "Albanien", "+355"),
    EuropeanCountryDialCode("AD", "Andorra", "+376"),
    EuropeanCountryDialCode("AM", "Armenien", "+374"),
    EuropeanCountryDialCode("AT", "Österreich", "+43"),
    EuropeanCountryDialCode("AZ", "Aserbaidschan", "+994"),
    EuropeanCountryDialCode("BY", "Belarus", "+375"),
    EuropeanCountryDialCode("BE", "Belgien", "+32"),
    EuropeanCountryDialCode("BA", "Bosnien und Herzegowina", "+387"),
    EuropeanCountryDialCode("BG", "Bulgarien", "+359"),
    EuropeanCountryDialCode("HR", "Kroatien", "+385"),
    EuropeanCountryDialCode("CY", "Zypern", "+357"),
    EuropeanCountryDialCode("CZ", "Tschechien", "+420"),
    EuropeanCountryDialCode("DK", "Dänemark", "+45"),
    EuropeanCountryDialCode("EE", "Estland", "+372"),
    EuropeanCountryDialCode("FI", "Finnland", "+358"),
    EuropeanCountryDialCode("FR", "Frankreich", "+33"),
    EuropeanCountryDialCode("GE", "Georgien", "+995"),
    EuropeanCountryDialCode("DE", "Deutschland", "+49"),
    EuropeanCountryDialCode("GR", "Griechenland", "+30"),
    EuropeanCountryDialCode("HU", "Ungarn", "+36"),
    EuropeanCountryDialCode("IS", "Island", "+354"),
    EuropeanCountryDialCode("IE", "Irland", "+353"),
    EuropeanCountryDialCode("IT", "Italien", "+39"),
    EuropeanCountryDialCode("XK", "Kosovo", "+383"),
    EuropeanCountryDialCode("LV", "Lettland", "+371"),
    EuropeanCountryDialCode("LI", "Liechtenstein", "+423"),
    EuropeanCountryDialCode("LT", "Litauen", "+370"),
    EuropeanCountryDialCode("LU", "Luxemburg", "+352"),
    EuropeanCountryDialCode("MT", "Malta", "+356"),
    EuropeanCountryDialCode("MD", "Moldau", "+373"),
    EuropeanCountryDialCode("MC", "Monaco", "+377"),
    EuropeanCountryDialCode("ME", "Montenegro", "+382"),
    EuropeanCountryDialCode("NL", "Niederlande", "+31"),
    EuropeanCountryDialCode("MK", "Nordmazedonien", "+389"),
    EuropeanCountryDialCode("NO", "Norwegen", "+47"),
    EuropeanCountryDialCode("PL", "Polen", "+48"),
    EuropeanCountryDialCode("PT", "Portugal", "+351"),
    EuropeanCountryDialCode("RO", "Rumänien", "+40"),
    EuropeanCountryDialCode("RU", "Russland", "+7"),
    EuropeanCountryDialCode("SM", "San Marino", "+378"),
    EuropeanCountryDialCode("RS", "Serbien", "+381"),
    EuropeanCountryDialCode("SK", "Slowakei", "+421"),
    EuropeanCountryDialCode("SI", "Slowenien", "+386"),
    EuropeanCountryDialCode("ES", "Spanien", "+34"),
    EuropeanCountryDialCode("SE", "Schweden", "+46"),
    EuropeanCountryDialCode("CH", "Schweiz", "+41"),
    EuropeanCountryDialCode("TR", "Türkei", "+90"),
    EuropeanCountryDialCode("UA", "Ukraine", "+380"),
    EuropeanCountryDialCode("GB", "Vereinigtes Königreich", "+44"),
    EuropeanCountryDialCode("VA", "Vatikanstadt (über Italien)", "+39"),
)


def get_country_by_iso_code(iso_code: str | None) -> EuropeanCountryDialCode | None:
    if not iso_code:
        return None

    iso_code = iso_code.upper()
    return next((item for item in EUROPEAN_COUNTRY_DIAL_CODES if item.iso_code == iso_code), None)


def european_dial_code_choices() -> list[tuple[str, str]]:
    return [(item.iso_code, item.display_label) for item in EUROPEAN_COUNTRY_DIAL_CODES]
