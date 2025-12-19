"""Command-line interface for Guardian Content Stream."""

import sys
from datetime import date

import click

from guardian_stream.config import Config
from guardian_stream.exceptions import GuardianAPIError, PublisherError
from guardian_stream.guardian_client import GuardianClient
from guardian_stream.orchestrator import run
from guardian_stream.publisher import KinesisPublisher


def parse_date(ctx: click.Context, param: click.Parameter, value: str | None) -> date | None:
    """Parse date string in YYYY-MM-DD format."""
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise click.BadParameter(f"Invalid date format: {value}. Use YYYY-MM-DD.")


@click.command()
@click.argument("search_term")
@click.option(
    "--date-from",
    callback=parse_date,
    help="Filter articles from this date (YYYY-MM-DD).",
)
def main(search_term: str, date_from: date | None) -> None:
    """Search The Guardian and publish articles to Kinesis.

    SEARCH_TERM: The query to search for (e.g., "machine learning").
    """
    try:
        config = Config()
    except Exception as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)

    try:
        client = GuardianClient(api_key=config.guardian_api_key)
        publisher = KinesisPublisher(stream_name=config.kinesis_stream_name)

        result = run(
            search_term=search_term,
            date_from=date_from,
            client=client,
            publisher=publisher,
        )

        click.echo(f"Found {result['articles_found']} articles for \"{search_term}\"")
        click.echo(f"Published {result['articles_published']} records to {config.kinesis_stream_name}")

    except GuardianAPIError as e:
        click.echo(f"Guardian API error: {e}", err=True)
        sys.exit(1)

    except PublisherError as e:
        click.echo(f"Publishing failed: {e}", err=True)
        sys.exit(1)

    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
