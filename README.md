# Glyph

## An architecture independent binary analysis tool for fingerprinting functions through NLP

![Black Hat Arsenal 2022](https://raw.githubusercontent.com/toolswatch/badges/master/arsenal/usa/2022.svg)

[![CodeQL](https://github.com/Xenios91/Glyph/actions/workflows/codeql.yml/badge.svg)](https://github.com/Xenios91/Glyph/actions/workflows/codeql.yml)
[![Pylint](https://github.com/Xenios91/Glyph/actions/workflows/pylint.yml/badge.svg)](https://github.com/Xenios91/Glyph/actions/workflows/pylint.yml)

Glyph Wiki: https://github.com/Xenios91/Glyph/wiki

Glyph API Documentation: http://localhost:5000/apidocs

Ghidra Script
https://github.com/Xenios91/Glyph-Ghidra

## Requirements

- Python version 3.9+
- Ghidra version 10+

## About

Reverse engineering is an important task performed by security researchers to identify vulnerable functions and malicious functions in IoT (Internet of Things) devices that are often shared across multiple devices of many system architectures. Common techniques to currently identify the reuse of these functions do not perform cross-architecture identification unless specific data such as unique strings are identified that may be of use in identifying a piece of code. Utilizing natural language processing techniques, Glyph allows you to upload an ELF binary (32 & 64 bit) for cross-architecture function fingerprinting, upon analysis, a web-based function symbol table will be created and presented to the user to aid in their analysis of binary executables/shared objects.

![Main Page](https://i.imgur.com/Gb9OFNN.png)



