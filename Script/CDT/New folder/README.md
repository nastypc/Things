# CDT Hover Converter

A VS Code extension that provides hover information for CDT files, displaying imperial conversions (feet-inches-sixteenths) for millimeter measurements.

## Features

- Hover over numeric values in CDT files to see their imperial equivalents
- Supports MiTek Structure CDT format coordinates
- Automatic conversion from millimeters to feet-inches-sixteenths format

## Requirements

- VS Code 1.74.0 or higher
- Node.js 16.x or higher

## Installation

1. Clone this repository
2. Run `npm install`
3. Press F5 to launch extension development host
4. In the new window, open a CDT file and hover over numbers

## Usage

Open a CDT file in VS Code. When you hover your mouse over a numeric value (representing millimeters), the extension will display the equivalent measurement in feet-inches-sixteenths format.

For example, hovering over `6096` will show: **6096 mm** = 20'

## Development

- `npm run compile` - Compile TypeScript
- `npm run watch` - Watch for changes and compile
- `npm run test` - Run tests

## Contributing

Contributions are welcome! Please open issues and pull requests on GitHub.