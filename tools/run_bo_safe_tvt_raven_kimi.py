"""Legacy safe_tvt_raven BO runner.

The old BO_list/terran/safe_tvt_raven/BO.json was removed after the dummy bot
switched to direct add-on construction. Regenerate a fresh BO.json before
re-enabling this runner.
"""


def main() -> None:
    raise SystemExit(
        "safe_tvt_raven BO.json has been removed; regenerate a fresh BO list "
        "before running this helper."
    )


if __name__ == "__main__":
    main()
