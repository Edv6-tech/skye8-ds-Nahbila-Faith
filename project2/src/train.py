"""Stage C commit 5.
Checks that fitting the pipeline on a fold's train rows does not let
the fold's validation rows into any fitted encoder.
Uses a broker id that only shows up in the validation half of a
small made up dataset, then checks the fitted onehot encoder never
learned that category.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pipeline import build_pipeline


def _toy_containers_with_val_only_broker():
    n_train = 12
    n_val = 3
    train_rows = {
        "gross_weight_kg": list(range(10, 10 + n_train * 10, 10)),
        "declared_value_xaf": list(range(100, 100 + n_train * 100, 100)),
        "value_per_kg": [10] * n_train,
        "value_per_kg_pct_in_chapter": [i / n_train for i in range(n_train)],
        "arrival_day_of_week": [i % 7 for i in range(n_train)],
        "arrival_month": [1] * n_train,
        "port_same_day_count": [1] * n_train,
        "port_trailing_week_count": list(range(n_train)),
        "teu_discharged": [100] * n_train,
        "container_teu": [1] * n_train,
        "vessel_teu_share": [0.01] * n_train,
        "broker_prior_count": list(range(n_train)),
        "broker_delay_rate": [i / n_train for i in range(n_train)],
        "importer_prior_count": list(range(n_train)),
        "importer_delay_rate": [i / n_train for i in range(n_train)],
        "container_type": ["20DV"] * n_train,
        "origin_port": ["Douala"] * n_train,
        "hs_chapter": [10] * n_train,
        "inspection_selected": [i % 2 == 0 for i in range(n_train)],
        "arrival_is_weekend": [False] * n_train,
        "vessel_missing": [False] * n_train,
        "broker_id": ["BK-001"] * n_train,
        "importer_id": ["IM-1"] * n_train,
        "delayed": [i % 2 for i in range(n_train)],
    }
    val_rows = {
        "gross_weight_kg": [40, 50, 60],
        "declared_value_xaf": [400, 500, 600],
        "value_per_kg": [10, 10, 10],
        "value_per_kg_pct_in_chapter": [0.4, 0.5, 0.6],
        "arrival_day_of_week": [3, 4, 5],
        "arrival_month": [1, 1, 1],
        "port_same_day_count": [1, 1, 1],
        "port_trailing_week_count": [3, 4, 5],
        "teu_discharged": [100, 100, 100],
        "container_teu": [1, 1, 1],
        "vessel_teu_share": [0.01, 0.01, 0.01],
        "broker_prior_count": [3, 4, 5],
        "broker_delay_rate": [0.3, 0.4, 0.5],
        "importer_prior_count": [3, 4, 5],
        "importer_delay_rate": [0.3, 0.4, 0.5],
        "container_type": ["20DV"] * n_val,
        "origin_port": ["Douala"] * n_val,
        "hs_chapter": [10] * n_val,
        "inspection_selected": [True, False, True],
        "arrival_is_weekend": [True, True, True],
        "vessel_missing": [False] * n_val,
        "broker_id": ["BK-002"] * n_val,
        "importer_id": ["IM-2"] * n_val,
        "delayed": [1, 0, 1],
    }
    train_df = pd.DataFrame(train_rows)
    val_df = pd.DataFrame(val_rows)
    return train_df, val_df


def test_onehot_encoder_never_learns_a_validation_only_category():
    train_fold, val_fold = _toy_containers_with_val_only_broker()

    pipe = build_pipeline("onehot")
    pipe.fit(train_fold, train_fold["delayed"])

    fitted_encoder = pipe.named_steps["preprocess"].named_transformers_["high_card_cat"].named_steps["onehot"]
    learned_categories = fitted_encoder.categories_

    broker_categories = learned_categories[0]
    importer_categories = learned_categories[1]

    assert "BK-002" not in broker_categories, "validation only broker leaked into the fitted encoder"
    assert "IM-2" not in importer_categories, "validation only importer leaked into the fitted encoder"
    assert "BK-001" in broker_categories
    assert "IM-1" in importer_categories

    pipe.predict_proba(val_fold)


def test_target_encoder_fit_only_uses_train_fold_rows():
    train_fold, val_fold = _toy_containers_with_val_only_broker()

    pipe = build_pipeline("target")
    pipe.fit(train_fold, train_fold["delayed"])

    fitted_encoder = pipe.named_steps["preprocess"].named_transformers_["high_card_cat"].named_steps["target_encode"]
    broker_categories = fitted_encoder.categories_[0]
    assert "BK-002" not in broker_categories, "validation only broker leaked into the fitted target encoder"

    pipe.predict_proba(val_fold)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))