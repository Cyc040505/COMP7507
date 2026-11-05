import sys, json, hashlib
from pathlib import Path
import numpy as np
from plotly.utils import PlotlyJSONEncoder
from src import data_loader as dl
from src.analytics.partners import flows
from src.analytics.geography import analyze
from src.modules import (
    overview as m0,
    m1_geography as m1,
    m2_economy as m2,
    m3_network as m3,
    m4_product as m4,
    m5_time as m5,
)


def chart(fig):
    return [
        {k: getattr(t, k, None) for k in ["type", "x", "y", "z", "customdata"]}
        for t in fig.data
    ]


result = {}
for year in [2010, 2023, 2024]:
    for mode in ["ranking", "six"]:
        a, b, _ = m0.figures(year, mode)
        result[f"M0-{year}-{mode}"] = [chart(a), chart(b)]
for country in ["CHN", "MEX"]:
    for product in ["TOTAL", "87"]:
        res = analyze(
            flows(2023, product),
            dl.load_geodist(),
            dl.load_country_meta(),
            country,
            2023,
            hs2=None if product == "TOTAL" else product,
            metric="dist",
        )
        result[f"M1-{country}-{product}"] = [
            chart(m1.scatter_figure(res)),
            res["stats"],
        ]
for mode in ["gdp", "export_value"]:
    for factor in [1.25, 1.5]:
        result[f"M2-{mode}-{factor}"] = chart(
            m2.scatter_figure(m2.data_for_year(2023), "DEU", "JPN", mode, factor)
        )
for country in ["CHN", "MEX"]:
    for direction in ["export", "import"]:
        for top in [5, 10, 20]:
            v = m3.figures(country, 2023, "87", direction, top, "matrix", None)
            result[f"M3-{country}-{direction}-{top}"] = [
                chart(v[0]),
                chart(v[1]),
                chart(v[2]),
                v[-1],
            ]
for mode in ["share", "rca"]:
    result[f"M4-{mode}"] = chart(
        m4.heat_figure(
            m4.metrics(2023),
            ["CHN", "MEX"],
            ["27", "29", "39", "84", "85", "87", "90", "95"],
            mode,
        )
    )
for product in ["85", "95", "87"]:
    result[f"M4-detail-{product}"] = chart(
        m4.detail_figure(m4.metrics(2023), "CHN", product)
    )
for product in ["TOTAL", "87"]:
    for metric in ["product", "intra"]:
        v = m5.compute_view(
            ["CHN", "DEU", "MEX"], product, 2019, 2020, [2016, 2024], metric, 2024
        )
        result[f"M5-{product}-{metric}"] = [
            chart(v["index"]),
            chart(v["structure"]),
            v["rows"],
            v["summary"],
        ]
result["protected_files"] = {
    str(p): hashlib.sha256(p.read_bytes()).hexdigest()
    for folder in ["data", "src/analytics"]
    for p in Path(folder).rglob("*")
    if p.is_file() and "__pycache__" not in str(p)
}
Path(sys.argv[1]).write_text(
    json.dumps(result, cls=PlotlyJSONEncoder, sort_keys=True, allow_nan=True)
)
print(
    "Saved",
    len(result) - 1,
    "figure scenarios and",
    len(result["protected_files"]),
    "protected files",
)
