"""
Stage C pipeline: every transformation - imputation, scaling, and
whichever broker/importer encoding is active - lives inside one
sklearn Pipeline, built fresh and fit only on that fold's training
rows. Nothing here is ever fit on the full dataset up front.

The brief asks for three ways of handling broker_id/importer_id to be
compared: leave them out, one-hot/ordinal, and out-of-fold target
encoding. build_pipeline's `high_card_encoding` argument switches
between them so the same fold-fitting code path is used for all three
- the comparison is then just "which encoding" varies, not "how the
fold is fit".
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler, TargetEncoder

# Engineered numeric features from Stage B, plus the raw numeric
# columns that were already on the container's own row.
NUMERIC_FEATURES = [
    "gross_weight_kg",
    "declared_value_xaf",
    "value_per_kg",
    "value_per_kg_pct_in_chapter",
    "arrival_day_of_week",
    "arrival_month",
    "port_same_day_count",
    "port_trailing_week_count",
    "teu_discharged",
    "container_teu",
    "vessel_teu_share",
    "broker_prior_count",
    "broker_delay_rate",
    "importer_prior_count",
    "importer_delay_rate",
]

# Low-cardinality categoricals that are always one-hot encoded,
# regardless of what we're doing with broker/importer. hs_chapter is
# numeric-looking but is a code, not a quantity - one-hotting it
# avoids implying a false ordering (chapter 48 isn't "more" than
# chapter 29).
LOW_CARD_CATEGORICAL = ["container_type", "origin_port", "hs_chapter"]

BOOLEAN_FEATURES = ["inspection_selected", "arrival_is_weekend", "vessel_missing"]

HIGH_CARD_CATEGORICAL = ["broker_id", "importer_id"]

HighCardEncoding = Literal["drop", "onehot", "target"]


def build_preprocessor(high_card_encoding: HighCardEncoding) -> ColumnTransformer:
    """One ColumnTransformer, built fresh each call. Nothing inside it
    is fit yet - fitting happens later, per fold, in build_pipeline's
    caller.
    """
    numeric_pipeline = Pipeline(
        steps=[
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )

    low_card_pipeline = Pipeline(
        steps=[
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    bool_pipeline = Pipeline(
        steps=[
            # SimpleImputer rejects raw bool dtype outright - this is
            # a plain dtype cast, not a fitted statistic, so doing it
            # unconditionally (not "inside the fold") introduces no
            # leakage; there's no information from other rows
            # involved, just True/False -> 1.0/0.0.
            ("to_float", FunctionTransformer(lambda X: X.astype("float64"))),
            ("impute", SimpleImputer(strategy="most_frequent")),
        ]
    )

    transformers = [
        ("numeric", numeric_pipeline, NUMERIC_FEATURES),
        ("low_card_cat", low_card_pipeline, LOW_CARD_CATEGORICAL),
        ("boolean", bool_pipeline, BOOLEAN_FEATURES),
    ]

    if high_card_encoding == "onehot":
        high_card_pipeline = Pipeline(
            steps=[
                ("impute", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ]
        )
        transformers.append(("high_card_cat", high_card_pipeline, HIGH_CARD_CATEGORICAL))
    elif high_card_encoding == "target":
        # sklearn's TargetEncoder does its own internal cross-fitting
        # when .fit_transform is called on training data (it splits
        # training rows into internal folds so a category's encoded
        # value is never derived from including the row it's being
        # applied to). This is what keeps it safe to use inside our
        # own outer folds - it does not need our fold's y elsewhere.
        high_card_pipeline = Pipeline(
            steps=[
                ("impute", SimpleImputer(strategy="most_frequent")),
                ("target_encode", TargetEncoder(target_type="binary")),
            ]
        )
        transformers.append(("high_card_cat", high_card_pipeline, HIGH_CARD_CATEGORICAL))
    elif high_card_encoding != "drop":
        raise ValueError(f"Unknown high_card_encoding: {high_card_encoding!r}")
    # "drop": simply don't add broker_id/importer_id to any transformer,
    # so ColumnTransformer's default remainder="drop" excludes them.

    return ColumnTransformer(transformers=transformers, remainder="drop")


def build_pipeline(
    high_card_encoding: HighCardEncoding,
    model=None,
) -> Pipeline:
    """Full pipeline: preprocessing + model, as one object. Calling
    .fit(X_train, y_train) on this fits EVERYTHING - the imputers,
    the scaler, the encoders, and the model - using only X_train,
    y_train. Nothing here has seen validation-fold or held-out data
    at the point .fit is called.
    """
    if model is None:
        model = HistGradientBoostingClassifier(random_state=42)

    return Pipeline(
        steps=[
            ("preprocess", build_preprocessor(high_card_encoding)),
            ("model", model),
        ]
    )