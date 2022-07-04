#!/usr/bin/env python3

import asyncio

from gui import app


def main() -> None:
    """GUI entry point."""
    asyncio.run(app())


if __name__ == '__main__':
    main()
