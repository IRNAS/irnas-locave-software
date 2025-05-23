# Irnas LoCave software

Python implementation of Locave base software. It contains everything we need to setup a new base
unit on Raspberry Pi:

- simple web server for browser based user interface
- Telegram bot for Telegram integration
- implementation of LoCave serial communication protocol, for communication with first node in
  network

## Checklist

### General GitHub setup

- [ ] Provide a concise and accurate description of your project in the GitHub "description" field.
- [ ] Provide a concise and accurate description of your project in this `README.md` file, replace
      the title.
- [x] Ensure that your project follows [repository naming scheme].

### Tooling

- [x] Turn on `pre-commit` tool by running `pre-commit install`. If you do not have it yet, follow
      instructions
      [here](https://github.com/IRNAS/irnas-guidelines-docs/tree/main/tools/pre-commit).

### Cleanup

- [x] Remove any files and folders that your project doesn't require. This avoid possible multiple
      definition issues down the road and keeps your project clean from redundant files.
- [ ] As a final step delete this checklist and commit changes.
