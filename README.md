# Stellenbosch Weather services

This repository contains processing scripts that need to run periodically.
The most important part is importing weather data from the weather stations.
In the future this can be extended to aggregate data for graphing.

## Configuration

The scripts look for `settings.conf` in this order:

1. The current working directory (`./settings.conf`).
2. The services repository root.
3. The parent workspace directory.
4. The current user's home directory (`~/settings.conf`).
