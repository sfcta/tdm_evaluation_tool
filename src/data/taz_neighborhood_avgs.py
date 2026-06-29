"""
Calculate neighborhood averages of TAZ attributes by (walk skims) distance from each TAZ

Used e.g. to calculate neighborhood parking availability rates
"""

USAGE = r"""
  python taz_avg_attributes_by_skim.py config_file.py input_dir

  Gets the network skim distance from a walkSkim file, and averages some 
  Reads the following input files from input_dir:
  * input file with TAZ as a key and some attribute to be averaged
  * walkSkim.h5
  
  Outputs the following:
  * taz_network_average.csv
"""
# import argparse  # use config.toml in repo
import sys
import tomllib
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, r"Y:\champ\dev\7CE.0.0_dev\lib")
import Lookups
import SkimUtil


def load_walk_skim_distances(walk_skim_dir, sf_only: bool):
    """Read walk distances from skims."""
    walk_skim = SkimUtil.WalkSkim(walk_skim_dir)
    walk_skim_distances_od = walk_skim.getSkimTable("DISTANCE")
    if sf_only:
        walk_skim_distances_od = walk_skim_distances_od[
            : Lookups.MAX_SF_COUNTY_ZONE, : Lookups.MAX_SF_COUNTY_ZONE
        ]
    if np.isnan(walk_skim_distances_od).any():
        raise ValueError("Walk skim distances contain NaN values.")
    return walk_skim_distances_od


def average_od_matrix_pairs(od_matrix: np.ndarray):
    """Average OD matrix pairs (i.e. assume symmetry and non-directional)
    such that A<->B = mean(A->B, B->A)."""
    return (od_matrix + od_matrix.T) / 2


def od_matrix_to_long_df(od_matrix: np.ndarray, value_name):
    """Convert walk skim distances numpy array to long form polars DataFrame."""
    # TODO VERIFY unclear whether rows or cols are origin or destinations for Cube Skims
    if not np.allclose(od_matrix, od_matrix.T):
        raise NotImplementedError(
            "TO VERIFY: Whether rows or cols are origin or destinations for Cube Skims."
        )
    row_ids, col_ids = np.indices(od_matrix.shape)
    od_long_df = pl.DataFrame(
        {
            # +1: numpy is 0 indexed, TAZs are 1 indexed
            "origin_taz": row_ids.flatten() + 1,
            "destination_taz": col_ids.flatten() + 1,
            value_name: od_matrix.flatten(),
        }
    )
    return od_long_df


def load_taz_sums(
    taz_data_filepath,
    key_field="taz",
    fields_to_sum=["spaces_est", "resunits"],
    null_default=0,
    # fields_to_sum: do not include parking_rate_est because it has to be recalculated
    # after grouping to each neighborhood and summing spaces_est and resunits
):
    """Read TAZ-level data and sum to taz level."""
    if key_field != "taz":
        raise NotImplementedError("only doing TAZ handling at this stepo")
    tazdata_df = pl.read_csv(
        taz_data_filepath,
        columns=[key_field] + fields_to_sum,
        schema_overrides={key_field: pl.Int64},  # taz
    )
    taz_sums = (
        tazdata_df.group_by(key_field)
        .agg(pl.col(fields_to_sum).sum())
        .with_columns(pl.col(fields_to_sum).fill_null(null_default))
    )
    return taz_sums


if __name__ == "__main__":
    # parser = argparse.ArgumentParser(description=USAGE)
    # parser.add_argument("config_toml_filepath")
    # args = parser.parse_args()

    # with open(args.config_toml_filepath, "rb") as f:
    with open("../config.toml", "rb") as f:
        config = tomllib.load(f)

    data_dir = Path(config["data_dir"])
    interim_dir = data_dir / config["interim"]["PATH"]
    taz_data_filepath = interim_dir / config["interim"]["TAZ_PARKING"]  # input
    # output
    neighborhood_data_filepath = interim_dir / config["interim"]["NEIGHBORHOOD_PARKING"]
    walk_skim_dir = data_dir / config["raw"]["PATH"]  # dir with walkSkim.h5

    # Create timeperiod duration combinations: EA-EA, EA-AM, etc
    TIMEPERIOD_DURATIONS = []
    for tpnum_start, tp_start in Lookups.Lookups.TIMEPERIODS_NUM_TO_STR.items():
        for tpnum_end, tp_end in Lookups.Lookups.TIMEPERIODS_NUM_TO_STR.items():
            if tpnum_start <= tpnum_end:
                TIMEPERIOD_DURATIONS.append("%s-%s" % (tp_start, tp_end))

    fields_to_sum = config["neighborhood_average_params"]["FIELDS_TO_SUM"]
    adjusted_fields_to_sum = [f"{field}_adjusted" for field in fields_to_sum]

    taz_sums = load_taz_sums(
        taz_data_filepath,
        key_field=config["neighborhood_average_params"]["KEY_FIELD"],
        fields_to_sum=fields_to_sum,
        null_default=config["neighborhood_average_params"]["NULL_DEFAULT"],
    )
    walk_skim_distances = od_matrix_to_long_df(
        average_od_matrix_pairs(
            # take average for each OD pair to calculate neighborhood averages,
            # i.e. assume non-directional and symmetrical
            load_walk_skim_distances(walk_skim_dir, sf_only=True)
        ),
        value_name="walk_distance",
    )
    taz_neighborhood_stats = (
        walk_skim_distances.filter(  # walk distances to nearby TAZs (in miles)
            (
                # Filter out unreachable
                (pl.col("walk_distance") > 0.0)  # 0 distance: unreachable TAZ
                &
                # Filter to Parking TAZs within distance threshold of the destination
                (
                    pl.col("walk_distance")
                    <= config["neighborhood_average_params"]["DISTANCE_TRESHOLD"]
                )
            )
            | (pl.col("origin_taz") == pl.col("destination_taz"))
        )
        # calculate exponential decay distance adjustment factor
        # for parking spaces and residential units
        .with_columns(
            distance_adjustment=(
                pl.col("walk_distance")
                * config["neighborhood_average_params"]["DISTANCE_COEFFICIENT"]
            ).exp()
        )
        # join with parking spaces and residential units of each nearby TAZ
        .rename({"origin_taz": "taz", "destination_taz": "nearby_taz"})
        .join(taz_sums, left_on="nearby_taz", right_on="taz", how="left")
        # calculate distance-adjusted parking spaces and residential units
        .with_columns(
            (pl.col(field) * pl.col("distance_adjustment")).alias(f"{field}_adjusted")
            for field in fields_to_sum
        )
        .group_by("taz")  # by origin_taz, now renamed "taz"
        .agg(
            # pl.col("nearby_taz").alias("nearby_tazs"),  # for testing only
            # pl.sum(fields_to_sum),  # for testing only
            pl.sum(adjusted_fields_to_sum),
            pl.len().alias("nearby_tazs_count"),
        )
        .with_columns(
            # HOTFIX hardcoded, instead of set in config toml
            parking_ratio_adjusted=(
                pl.col("spaces_est_adjusted") / pl.col("resunits_adjusted")
            )
        )
        .select(
            "taz",
            # "nearby_tazs",  # for testing only
            "nearby_tazs_count",
            # *fields_to_sum,  # for testing only
            *adjusted_fields_to_sum,
            "parking_ratio_adjusted",  # HOTFIX hardcoded, instead of set in config toml
        )
        .sort("taz")
    )
    taz_neighborhood_stats.write_csv(neighborhood_data_filepath)
    print(f"Wrote {neighborhood_data_filepath}")
