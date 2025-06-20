# TranslateFileTools

## Description

The tool uses Google's Gemini API to support translating supported files into another language, supporting multi-threading to speed up translation.

## Getting Started

### Prerequisites

List any software or libraries that need to be installed before running the project.  Include links to their official websites or installation instructions.  For example:

*   Python 3.7+
*   [pip](https://pip.pypa.io/en/stable/installation/)
*   Gemini API Key

### Installation

Provide clear, step-by-step instructions on how to set up and install your project. Include code snippets for commands that need to be run.

```bash
# Create Python environment
python -m venv venv
```
# Activate environment and install packages
```bash
# On Windows:
call venv\Scripts\activate

# On Linux/macOS:
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```
### Installation

Explain any necessary configuration steps. If your project requires environment variables, describe how to set them up. For example:

Create a `.env` file in the project's root directory.

Add your Gemini API key to the `.env` file:

```.env
GEMINI_API_KEY='YOUR_ACTUAL_API_KEY_HERE'
```
### Start Tools
To start and use the tool, run the following command:
```bash
# Run the main script
python translate_file_tool_v3.py
```
### License
```license
MIT License

Copyright (c) 2025 KennjiHayakawa

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
