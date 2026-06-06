"""
Create neighborhood averages of TAZ attributes (e.g parking supply) by distance from the
TAZ, using the walk skim to determine distance.
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

import polars as pl

sys.path.insert(0, r"Y:\champ\dev\7CE.0.0_dev\lib")
import Lookups
import SkimUtil

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

    tazdata_df = pl.read_csv(
        taz_data_filepath,
        columns=["taz", "spaces_est", "resunits"],
        # do not include parking_rate_est because it has to be recalculated after
        # grouping to each neighborhood and summing spaces_est and resunits
    )

    # 2. Sum to TAZ
    neighborhood_sums = tazdata_df.group_by(
        config["neighborhood_average_params"]["KEY_FIELD"]
    ).agg(pl.col(config["neighborhood_average_params"]["FIELDS_TO_SUM"]).sum())

    # Read Walk Distances from Skims
    walk_skim = SkimUtil.WalkSkim(walk_skim_dir)
    walk_dist = walk_skim.getSkimTable("DISTANCE")

    results = []  # list of dictionaries
    for home_taz in range(1, Lookups.MAX_SF_ZONE + 1):
        # in miles
        walk_distances = walk_dist[: Lookups.MAX_SF_ZONE, home_taz - 1]  # 0-index
        nearby_tazs = (
            pl.DataFrame(
                {
                    "Nearby TAZ": range(1, 1 + len(walk_distances)),
                    "Walk Distance": walk_distances,
                }
            )
            .filter(
                (
                    # Filter out unreachable
                    (pl.col("Walk Distance") > 0.0)  # 0 distance: unreachable TAZ
                    &
                    # Filter to Parking TAZs within distance threshold of the destination
                    (
                        pl.col("Walk Distance")
                        <= config["neighborhood_average_params"]["DISTANCE_TRESHOLD"]
                    )
                )
                | (pl.col("Nearby TAZ") == home_taz)
            )
            .with_columns(
                distance_adjustment=(
                    pl.col("Walk Distance")
                    * config["neighborhood_average_params"]["DISTANCE_COEFFICIENT"]
                ).exp()
            )
        )
        if nearby_tazs.height == 0:
            # print("0 walking distance TAZs: skipping")
            continue
        assert nearby_tazs.select("Walk Distance").null_count() == 0
        # print "Destination TAZ %3d" % home_taz
        # print "  %3d Parking TAZs within %.2f miles" % (len(dest_df), config["DISTANCE_TRESHHOLD"])

        # Identify distance to all sites within distance threshold
        # Join with Off-Street info
        nearby_tazs = nearby_tazs.join(
            neighborhood_sums, left_on="Nearby TAZ", right_on="TAZ", how="left"
        )
        # sum fields in config["neighborhood_average_params"]["FIELDS_TO_SUM"]
        # for field in config["neighborhood_average_params"]["FIELDS_TO_SUM"]:
        #     TODO verify: shouldn't be needed! if this is needed, probably do fill_nan:
        #     # Fill in NaN Off-Street Capacity with default
        #     dest_df.loc[pd.isnull(dest_df[field]), field] = config[
        #         "neighborhood_average_params"
        #     ]["NA_DEFAULT"]
        result_dict = {
            "TAZ": home_taz,
            "CountOfNearbyTAZs": nearby_tazs.height,
        } | {
            col: nearby_tazs[col].sum().item()
            for col in config["neighborhood_average_params"]["FIELDS_TO_SUM"]
        }

        # HOTFIX hardcoded, instead of set in config toml
        result_dict["parking_ratio_nodistancedecay"] = (
            result_dict["spaces_est"] / result_dict["resunits"]
        )

        results.append(result_dict)

    result_df = pl.DataFrame(results)
    # reorder columns
    cols = ["TAZ", "CountOfNearbyTAZs"]
    for field in config["neighborhood_average_params"]["FIELDS_TO_SUMMARIZE"]:
        cols.append(field)
    result_df = result_df[cols]
    result_df.fillna(0, inplace=True)
    result_df.to_csv(neighborhood_data_filepath, index=False, float_format="%.4f")
    print(f"Wrote {neighborhood_data_filepath}")
