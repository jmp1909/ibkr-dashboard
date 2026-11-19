"""
Tests for fund_data.py: grouping countries, reading categories, merging with
config.json, the cache, and the Vanguard and iShares parsers.

Offline: every network call is replaced by a canned response.
Run with:  python -m unittest discover tests
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import fund_data as fd  # noqa: E402


class FakeResponse:
    def __init__(self, body, content_type="application/json", ok=True):
        self.ok, self.headers = ok, {"content-type": content_type}
        self._body = body
        self.text = body if isinstance(body, str) else json.dumps(body)

    def json(self):
        return self._body if not isinstance(self._body, str) else json.loads(self._body)

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError("HTTP error")


class FakeSession:
    """Answers each GET from a {url substring: response} table."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def get(self, url, headers=None, timeout=None):
        self.calls.append(url)
        for part, resp in self.routes.items():
            if part in url:
                return resp
        return FakeResponse("<html>not found</html>", "text/html", ok=False)


VT_COUNTRIES = {"United States": 63.0, "Japan": 5.9, "Korea": 2.1, "Poland": 0.3, "China": 2.5,
                "France": 2.0, "United Kingdom": 3.2, "Switzerland": 2.0, "Canada": 3.0}


class Categories(unittest.TestCase):
    def test_single_region_categories(self):
        self.assertEqual(fd.split_from_category("Small Value"), {"us": 1.0, "dev": 0.0, "em": 0.0})
        self.assertEqual(fd.split_from_category("Mid-Cap Blend")["us"], 1.0)
        self.assertEqual(fd.split_from_category("Foreign Small/Mid Value")["dev"], 1.0)
        self.assertEqual(fd.split_from_category("Diversified Emerging Mkts")["em"], 1.0)
        self.assertEqual(fd.split_from_category("China Region")["em"], 1.0)

    def test_categories_that_cannot_tell(self):
        for c in ("Global Large-Stock Blend", "Technology", "", None):
            self.assertIsNone(fd.split_from_category(c))

    def test_tilt_from_category_or_name(self):
        self.assertEqual(fd.tilt_from_category("Small Value"), 1)
        self.assertEqual(fd.tilt_from_category("Diversified Emerging Mkts", "Avantis Emerging Markets Value ETF"), 1)
        self.assertEqual(fd.tilt_from_category("Global Large-Stock Blend", "Vanguard Total World"), 0)
        self.assertIsNone(fd.tilt_from_category(None, None))


class Countries(unittest.TestCase):
    def test_msci_counts_korea_and_poland_as_emerging(self):
        m = fd.split_from_countries(VT_COUNTRIES, "msci")
        f = fd.split_from_countries(VT_COUNTRIES, "ftse")
        self.assertAlmostEqual(m["em"] - f["em"], (2.1 + 0.3) / sum(VT_COUNTRIES.values()), places=3)
        self.assertAlmostEqual(sum(m.values()), 1.0, places=3)

    def test_names_are_normalised_and_junk_ignored(self):
        s = fd.split_from_countries({"Korea (South)": 10, "  United   States ": 10, "-": 50, "Turkiye": 10})
        self.assertEqual(s, {"us": round(1 / 3, 4), "dev": 0.0, "em": round(2 / 3, 4)})

    def test_empty_list_gives_nothing(self):
        self.assertIsNone(fd.split_from_countries({}))
        self.assertIsNone(fd.split_from_countries({"-": 100}))

    def test_currencies_by_home_country(self):
        b = fd.basket_from_countries({"United States": 50, "Germany": 10, "Greece": 5, "Japan": 10,
                                      "United Kingdom": 5, "Switzerland": 5, "Canada": 5, "India": 10})
        self.assertEqual(b, {"USD": 0.5, "EUR": 0.15, "JPY": 0.1, "Emerging": 0.1,
                             "GBP": 0.05, "CHF": 0.05, "Other developed": 0.05})

    def test_korea_currency_follows_the_scheme(self):
        self.assertEqual(fd.basket_from_countries({"Korea": 1}, "msci"), {"Emerging": 1.0})
        self.assertEqual(fd.basket_from_countries({"Korea": 1}, "ftse"), {"Other developed": 1.0})


class Merge(unittest.TestCase):
    fetched = {
        "VT": {"countries": VT_COUNTRIES, "split_source": "Vanguard", "tilt": 0, "ter": 0.0006,
               "ter_source": "Vanguard", "role": "Global Large-Stock Blend"},
        "AVUV": {"us": 1.0, "dev": 0.0, "em": 0.0, "split_source": "fund category", "tilt": 1, "ter": 0.0025},
        "AVES": {"us": 0.0, "dev": 0.0, "em": 1.0, "split_source": "fund category"},
        "AVDV": {"us": 0.0, "dev": 1.0, "em": 0.0, "split_source": "fund category"},
    }
    proxy = {"countries": {"United States": 5, "Japan": 40, "Korea": 20, "France": 40}}

    def test_fetched_only(self):
        m = fd.merge(self.fetched, {}, "msci", self.proxy)
        self.assertEqual(m["VT"]["source"], "Vanguard")
        self.assertAlmostEqual(m["VT"]["us"] + m["VT"]["dev"] + m["VT"]["em"], 1.0, places=3)
        self.assertEqual(m["AVUV"]["basket"], {"USD": 1.0})
        self.assertEqual(m["AVES"]["basket"], {"Emerging": 1.0})

    def test_developed_fund_borrows_proxy_without_us_or_emerging(self):
        b = fd.merge(self.fetched, {}, "msci", self.proxy)["AVDV"]
        self.assertEqual(b["basket"], {"JPY": 0.5, "EUR": 0.5})
        self.assertIn("estimate", b["basket_source"])
        # under FTSE, Korea is developed and stays in
        self.assertIn("Other developed", fd.merge(self.fetched, {}, "ftse", self.proxy)["AVDV"]["basket"])

    def test_no_proxy_no_guess(self):
        self.assertNotIn("basket", fd.merge(self.fetched, {}, "msci", None)["AVDV"])

    def test_config_split_replaces_whole_split(self):
        m = fd.merge(self.fetched, {"VT": {"us": 0.6, "dev": 0.3}}, "msci")
        self.assertEqual((m["VT"]["us"], m["VT"]["dev"], m["VT"]["em"]), (0.6, 0.3, 0.0))
        self.assertEqual(m["VT"]["source"], "config.json")

    def test_config_fields_override_one_by_one(self):
        m = fd.merge(self.fetched, {"VT": {"role": "Core", "ter": 0.001}}, "msci")
        self.assertEqual(m["VT"]["role"], "Core")
        self.assertEqual((m["VT"]["ter"], m["VT"]["ter_source"]), (0.001, "config.json"))
        self.assertEqual(m["VT"]["source"], "Vanguard")  # split untouched

    def test_config_only_fund(self):
        m = fd.merge({}, {"XYZ": {"us": 1}}, "msci")
        self.assertEqual(m["XYZ"], {"us": 1.0, "dev": 0.0, "em": 0.0, "source": "config.json"})


class Sources(unittest.TestCase):
    def test_vanguard_falls_back_to_fund_number(self):
        broken = FakeResponse({"response": "error calling ..."})
        items = [{"name": "Japan   ", "currYrPct": "40"}, {"name": "China", "currYrPct": "60"},
                 {"name": "Other", "prevYrPct": "1"}]
        s = FakeSession({
            "/vmf/api/VXUS/": broken,
            "/etfs/profile/vxus": FakeResponse('... fundId&#34;:&#34;3369&#34; ...', "text/html"),
            "/vmf/api/3369/diversification": FakeResponse({"country": {"item": items}}),
            "/vmf/api/3369/expense": FakeResponse({"expenseRatio": "0.0500"}),
        })
        out = fd.from_vanguard("VXUS", s)
        self.assertEqual(out["countries"], {"Japan": 40.0, "China": 60.0})
        self.assertEqual(out["ter"], 0.0005)

    def test_ishares_holdings_file(self):
        csv_text = ('iShares MSCI ACWI ETF\nFund Holdings as of,"Nov 18, 2026"\n\n'
                    'Ticker,Name,Sector,Asset Class,Market Value,Weight (%),Location\n'
                    '"AAPL","APPLE","IT","Equity","1","60.00","United States"\n'
                    '"7203","TOYOTA","Cons","Equity","1","25.00","Japan"\n'
                    '"SAP","SAP","IT","Equity","1","15.00","Germany"\n'
                    '"USD","USD CASH","Cash","Cash","1","1.00","United States"\n')
        s = FakeSession({
            "product-screener": FakeResponse({"1": {"localExchangeTicker": "ACWI", "productPageUrl": "/us/products/1/acwi"}}),
            "/us/products/1/acwi/latest-holdings.csv": FakeResponse(csv_text, "text/plain"),
        })
        ish = fd.IShares(s)
        self.assertEqual(ish.countries("ACWI"), {"United States": 60.0, "Japan": 25.0, "Germany": 15.0})
        self.assertIsNone(ish.countries("NOPE"))
        self.assertEqual(sum("product-screener" in c for c in s.calls), 1)  # list fetched once


class Cache(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "fund_data.json"

    def tearDown(self):
        self.dir.cleanup()

    def write(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")

    def test_fresh_cache_is_not_refetched(self):
        self.write({"VT": {"us": 1.0, "fetched": datetime.now().isoformat()}})
        with mock.patch.object(fd, "fetch_one", side_effect=AssertionError("fetched")):
            self.assertEqual(fd.load(["vt"], self.path)["VT"]["us"], 1.0)

    def test_stale_entry_is_refetched(self):
        old = (datetime.now() - timedelta(days=30)).isoformat()
        self.write({"VT": {"us": 0.5, "fetched": old}})
        with mock.patch.object(fd, "fetch_one", return_value={"us": 0.6, "dev": 0.4, "em": 0.0}):
            c = fd.load(["VT"], self.path)
        self.assertEqual(c["VT"]["us"], 0.6)
        self.assertEqual(json.loads(self.path.read_text())["VT"]["us"], 0.6)  # saved

    def test_failed_source_keeps_real_country_list(self):
        old = (datetime.now() - timedelta(days=30)).isoformat()
        self.write({"VT": {"countries": VT_COUNTRIES, "split_source": "Vanguard", "fetched": old}})
        guess = {"us": 0.0, "dev": 1.0, "em": 0.0, "split_source": "fund category", "ter": 0.0007}
        with mock.patch.object(fd, "fetch_one", return_value=guess):
            c = fd.load(["VT"], self.path)["VT"]
        self.assertEqual((c["countries"], c["split_source"]), (VT_COUNTRIES, "Vanguard"))
        self.assertNotIn("us", c)
        self.assertEqual(c["ter"], 0.0007)  # the rest is still updated

    def test_nothing_fetched_keeps_cache(self):
        old = (datetime.now() - timedelta(days=30)).isoformat()
        self.write({"VT": {"us": 0.5, "fetched": old}})
        with mock.patch.object(fd, "fetch_one", return_value=None):
            self.assertEqual(fd.load(["VT"], self.path)["VT"]["us"], 0.5)

    def test_missing_yfinance_does_not_raise(self):
        with mock.patch.object(fd, "fetch_one", side_effect=ImportError("yfinance")):
            self.assertEqual(fd.load(["VT"], self.path), {})


class ConfigOverrides(unittest.TestCase):
    def test_currency_basket_in_config_wins(self):
        import main

        lt = {"VT": {"basket": {"USD": 0.6, "EUR": 0.4}, "basket_source": "Vanguard"},
              "AVDV": {"basket": {"EUR": 1.0}, "basket_source": "estimate"}}
        baskets, sources = main.resolve_baskets({"currency_basket": {"AVDV": {"JPY": 1.0}}}, lt)
        self.assertEqual(baskets, {"VT": {"USD": 0.6, "EUR": 0.4}, "AVDV": {"JPY": 1.0}})
        self.assertEqual(sources, {"VT": "Vanguard", "AVDV": "config.json"})


if __name__ == "__main__":
    unittest.main()
