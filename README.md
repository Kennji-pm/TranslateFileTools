# TranslateFileTools

## Description

TranslateFileTools is a command-line utility designed to translate various file types into different languages. It leverages the Google Gemini API for translation and incorporates multi-threading to significantly speed up the translation process, making it efficient for large files or multiple documents.

## Getting Started

### Prerequisites

Before you begin, ensure you have the following installed on your system:

* Python 3.7+: You can download Python from the official [Python website](https://www.python.org/downloads).

* pip: This is Python's package installer and usually comes bundled with Python installations.

* Gemini API Key: You'll need an API key from Google to use the Gemini API. You can obtain one by following the instructions on the [Google AI Studio website](https://ai.google.dev/).

### Installation

Follow these steps to set up and install the project:

#### **1.** Clone the Repository:

Clone this repository to your local machine:
```bash
git clone https://github.com/KennjiHayakawa/TranslateFileTools.git
cd TranslateFileTools
```

#### **2.** Create a Python Virtual Environment:

It's recommended to use a virtual environment to manage project dependencies. This isolates the project's packages from your system-wide Python installation.

```bash
python -m venv venv
```
#### **3.** Activate the Virtual Environment:
* On Windows:
```bash
call venv\Scripts\activate
```
* On Linux:
```bash
source venv/bin/activate
```

#### **4.** Install Required Packages:
Once your virtual environment is active, install the necessary Python packages using pip:
```bash
pip install -r requirements.txt
```
*(**Note:** Ensure you have a requirements.txt file in your project's root directory listing all dependencies.)*

### Configuration

This tool requires your Gemini API Key for authentication.

1. Create a `.env` file:

    In the root directory of your project, create a new file named .env.

1. Add your Gemini API Key:

    Open the newly created .env file and add the following line, replacing `'YOUR_ACTUAL_API_KEY_HERE'` with your actual Gemini API key:

```env
GEMINI_API_KEYS='YOUR_ACTUAL_API_KEY_HERE'
```
*(**Note:** If you have multiple API keys, you can add more keys by inserting and separating them with commas..)*

### Running This Tools
To start and use the TranslateFileTools, execute the following command from your project's root directory (after activating your virtual environment):
```bash
python main.py
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
