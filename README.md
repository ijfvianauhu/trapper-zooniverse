# <img src="img/wildIntel_logo.webp" alt="Trapper Tools Logo" height="60">  Trapper Zooniverse

![Python](https://img.shields.io/badge/python-3.11-blue.svg)
![License](https://img.shields.io/badge/license-GPLv3-blue.svg)
![WildINTEL](https://img.shields.io/badge/WildINTEL-v1.0-blue)
![Trapper-client](https://img.shields.io/badge/trapper--client-v1.0-blue)
![Trapper-browser](https://img.shields.io/badge/trapper--browser-v1.0-blue)

<hr>

## CLI application for uploading Trapper collections to Zooniverse and publishing Zooniverse annotations back to Trapper


## 🚀 Features

- **Collections Upload**: Upload Trapper collections to Zooniverse subject sets
- **Annotations Upload**: Upload Zooniverse subject sets classification export to Tapper classification projects. 

## 📋 Requirements

- Python 3.11 or higher
- panoptes-client
- [Trapper client](https://github.com/ijfvianauhu/trapper-client)
- [Trapper Browser](https://github.com/ijfvianauhu/trapper-browser)
- Docker (optional, for running in a container)
- Access to a Trapper server instance
- Access to Zooniverse server 

## 🫎 Overview

A bridge for integrating [Trapper](https://gitlab.com/trapper-project/trapper) with [Zooniverse](https://www.zooniverse.org) projects 

Trapper-Zooniverse is a Python client that allows you to upload image collections from
[Trapper](https://gitlab.com/trapper-project/trapper) to [Zooniverse](https://www.zooniverse.org) subject sets 
and download classification from [Zooniverse](https://www.zooniverse.org) to [Trapper](https://gitlab.com/trapper-project/trapper) classification projects.

## 💻 Installation

wildintel-tools can be installed either using Docker or via a traditional Python virtual environment (venv). Docker
allows you to run the application in an isolated container with all dependencies included, while using a virtual 
environment lets you install and run it directly on your system.

### 🐳 Using Docker

The easiest way to install trapper-zooniverse is by using the provided Docker Compose file. Follow the steps below:

#### Step 1: Install Docker and Docker Compose

Follow the instructions for your operating system on the [Docker website](https://docs.docker.com/get-started/).


#### Step 2: Download docker-compose.yml

You can download the `docker-compose.yml` file from here or clone this repository:

```bash
git clone https://github.com/ijfvianauhu/trapper-zooniverse.git
cd trapper-zooniverse
```

#### Step 3: Set up a directory to share data between host and  container

On the host machine where Docker is running, you need to have a directory to share data between the host and the container.

To make this directory accessible inside the Docker container, you must set the `DATA_PATH` environment variable to this 
main directory. To set up this variable, copy the `env.example` file located in the root directory of this repository 
to a `.env` file located in the same directory as `docker-compose.yml`. Once copied, edit the `.env` file and update 
the values of `DATA_PATH` environment variable.

```bash
# Linux bash
cp env.example .env
vi .env
DATA_PATH=./wildintel-tools-data/
```
> **Note:** The `.env` file can also include your trapper-zooniverse global settings. See the example provided in this 
> repository: env.example.

Optionally, you can also set the DATA_PATH environment variable directly in your shell before starting the Docker container:

```bash
# Linux bash 
export DATA_PATH=/path/to/trapper-zooniverse-data/
# Windows PowerShell
$env:DATA_PATH = "C:\path\to\trapper-zooniverse-data\"
```

#### Step 4: Start the Docker container and open a terminal inside it

From the directory where `docker-compose.yml` is located, run the following command to start the container:

``` bash
docker compose up -d
docker compose exec --user trapper trapper-zooniverse bash
```

> **Note** : To update the container to the latest version, run `docker compose pull` before starting it.

#### Step 5: Run trapper-tools commands

You can now run `trapper-zooniverse` commands inside the container. Refer to the Usage section for available commands. 
For now, let's verify that everything is working by running:

```
trapper-zooniverse --help 
```

You should see the following output:

```
Usage: trapper-zooniverse [OPTIONS] COMMAND [ARGS]...                                                                                                                                                   
                                                                                                                                                                                                         
 CLI for uploading images from Trapper to Zooniverse and upload Zooniverse results to Trapper                                                                                                            
                                                                                                                                                                                                         
╭─ Options ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --version               --no-version             Show program's version number and exit                                                                                                               │
│ --verbosity                             INTEGER  Logger level: 0 (error), 1 (info), 2 (debug).                                                                                                        │
│ --logfile                               PATH     Path to the log file                                                                                                                                 │
│                                                  [default: /home/ijfviana/.config/trapper-zooniverse/app.log]                                                                                         │
│ --env-file                                       Load .env file with dotenv                                                                                                                           │
│ --settings-dir                          PATH     Directory containing settings files                                                                                                                  │
│                                                  [default: /home/ijfviana/.config/trapper-zooniverse]                                                                                                 │
│ --install-completion                             Install completion for the current shell.                                                                                                            │
│ --show-completion                                Show completion for the current shell, to copy it or customize the installation.                                                                     │
│ --help                                           Show this message and exit.                                                                                                                          │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ collections-upload   Upload all media (images) from a Trapper collection to a Zooniverse subject set                                                                                                  │
│ annotations-upload   Upload all annotations from a Zooniverse subject set to a Trapper classification project                                                                                         │
│ config               Manage project configurations                                                                                                                                                    │
│ logger               Manage project logger                                                                                                                                                            │
│ helpers              Helpers                                                                                                                                                                          │
│ reports              Manage project configurations                                                                                                                                                    │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

### ️️️⚙️ Using a a Python Virtual Environment (uv)

Alternatively, you can install trapper-zooniverse using a Python virtual environment. First, ensure you have [uv](https://github.com/astral-sh/uv) 
installed on your system:

```
# On macOS and Linux.
curl -LsSf https://astral.sh/uv/install.sh | sh
# On Windows.
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then, clone the repository and run the application:

```bash
git clone https://github.com/ijfvianauhu/trapper-zooniverse.git
cd trapper-zooniverse
```

After that, you can install `trapper-zooniverse` and its dependencies in an isolated environment using `uv`:

```bash

uv run trapper-zooniverse --help
```

You should see the following output:

```
Usage: trapper-zooniverse [OPTIONS] COMMAND [ARGS]...                                                                                                                                                   
                                                                                                                                                                                                         
 CLI for uploading images from Trapper to Zooniverse and upload Zooniverse results to Trapper                                                                                                            
                                                                                                                                                                                                         
╭─ Options ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --version               --no-version             Show program's version number and exit                                                                                                               │
│ --verbosity                             INTEGER  Logger level: 0 (error), 1 (info), 2 (debug).                                                                                                        │
│ --logfile                               PATH     Path to the log file                                                                                                                                 │
│                                                  [default: /home/ijfviana/.config/trapper-zooniverse/app.log]                                                                                         │
│ --env-file                                       Load .env file with dotenv                                                                                                                           │
│ --settings-dir                          PATH     Directory containing settings files                                                                                                                  │
│                                                  [default: /home/ijfviana/.config/trapper-zooniverse]                                                                                                 │
│ --install-completion                             Install completion for the current shell.                                                                                                            │
│ --show-completion                                Show completion for the current shell, to copy it or customize the installation.                                                                     │
│ --help                                           Show this message and exit.                                                                                                                          │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ collections-upload   Upload all media (images) from a Trapper collection to a Zooniverse subject set                                                                                                  │
│ annotations-upload   Upload all annotations from a Zooniverse subject set to a Trapper classification project                                                                                         │
│ config               Manage project configurations                                                                                                                                                    │
│ logger               Manage project logger                                                                                                                                                            │
│ helpers              Helpers                                                                                                                                                                          │
│ reports              Manage project configurations                                                                                                                                                    │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## ⚙️ Configuration

`trapper-zooniverse` uses [TOML](https://toml.io/en/) configuration files to manage application settings. You can have 
multiple configurations files for different Trapper server instances or Zooniverse projects and switch between them 
using the `--configuration` flag.

To simplify the creation and management of configuration files, trapper-zooniverse provides the `config` command:

```bash
wildintel-tools config --help  
                                                                                                                           
Usage: wildintel-tools config [OPTIONS] COMMAND [ARGS]...                                                                 
                                                                                                                           
Manage application configurations                                                                                             
                                                                                                                           
╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ──────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ init   Initialize a new application configuration                                                                           │
│ show   Validate and show current application settings                                                                       │
│ list   List all available application configurations                                                                        │
│ edit   Edit settings file in default editor                                                                             │
│ get    Display an application setting                                                                                        │
│ set    Set an application setting                                                                                            │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

For example, you can create new default configuration by running:

```
trapper-zooniverse config init
``` 
This command will create a default configuration file at the default settings directory 
(`~/.config/trapper-zooniverse/config.toml` on Linux and macOS, `%APPDATA%\trapper-zooniverse\config.toml` on Windows).

Then, this configuration file can be edited manually executing:

```
trapper-zooniverse config edit
```

Finally, you can view the current configuration by running:

```
trapper-zooniverse config show
```

### Configuration file structure
The configuration file is divided into several sections, each containing specific settings for different aspects of 
the application.  A sample default configuration might look like this:

```
[LOGGER]
loglevel = 1
filename = ""

[TRAPPER]
trapper_username= "trapper_client@uhu.es"
trapper_password= "pass"
trapper_url= "https://wildintel-trap.uhu.es/"
trapper_token= ""

[ZOONIVERSE]
zooniverse_username= ""
zooniverse_password= ""
zooniverse_project_id= ""

[ZOONIVERSE_CONNECTOR]
upload_collection_n_images_seq=5
upload_collection_max_interval=120
upload_collection_attempts=5
upload_collection_delay=15
upload_collection_max_attempts_per_subject=5
upload_collection_delay_seconds_per_subject=30
```
Each section is identified by a header enclosed in square brackets (e.g., `[TRAPPER]`, `[ZOONIVERSE]`), and contains
key-value pairs that define specific settings.

#### 🧾 [LOGGER]

This section contains settings related to logging behavior. These settings help control how much information is logged 
and where the log files are stored. Table below describes each variable in this section:


| Variable            | Description                                                                          |
|---------------------| ------------------------------------------------------------------------------------ |
| `loglevel`          | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`).                                         |
| `filename`          | Path or name of the log file where client activity is recorded.                                               |


#### 🦙 [TRAPPER]

This section contains settings related to the Trapper server connection. These settings are used to authenticate
and interact with the Trapper server. Table below describes each variable in this section:

| Variable           | Description                                                                          |
|--------------------| ------------------------------------------------------------------------------------ |
| `trapper_username` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`).                                         |
| `trapper_password` | Path or name of the log file where client activity is recorded.                                               |
| `trapper_url`      | Path or name of the log file where client activity is recorded.                                               |
| `trapper_token`    | Path or name of the log file where client activity is recorded.                                               |

### 🦜 [ZOONIVERSE]
This section contains settings related to the Zooniverse server connection. These settings are used to authenticate
and interact with the Zooniverse server. Table below describes each variable in this section:

| Variable           | Description                                                                          |
|--------------------| ------------------------------------------------------------------------------------ |
| `zooniverse_username` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`).                                         |
| `zooniverse_password` | Path or name of the log file where client activity is recorded.                                               |
| `zooniverse_project_id`      | Path or name of the log file where client activity is recorded.                                               |

#### 🧩 [ZOONIVERSE_CONNECTOR]
This section contains settings related to the Zooniverse connector behavior. These settings help control how images
are uploaded to Zooniverse and how classifications are downloaded back to Trapper. Table below describes each variable
in this section:

| Variable           | Description                                                                          |
|--------------------| ------------------------------------------------------------------------------------ |
| `n_images_seq`              | Number of consecutive images per sequence uploaded as a single subject.         |
| `max_interval`              | Maximum allowed time interval (in seconds) between images in the same sequence. |
| `attempts`                  | Number of retry attempts when uploading fails.                                  |
| `delay`                     | Delay (in seconds) between retry attempts.                                      |
| `max_attempts_per_subject`  | Maximum number of upload attempts per subject before skipping it.               |
| `delay_seconds_per_subject` | Delay (in seconds) between subject uploads to prevent API overload.             |

## ⚡ Quick Start

Once you’ve installed [trapper-zooniverse](https://github.com/ijfvianauhu/trapper-zooniverse), you can start using it 
right away from the command line. Here’s what a typical first session looks like from a user’s perspective 

> **Note:** If the installation was done using uv, it is necessary to activate the virtual environment by running
> `source .venv/bin/activate`.

### ✅ Step 1: Check your configuration

First of all, initialize the configuration file by running:

```
trapper-zooniverse config init
```

Once this is done, edit it and modify the environment variables (typically the username, password, etc.) by running:

```
trapper-zooniverse config edit
```

To confirm changes in the configuration file, you can run:

```
trapper-zooniverse config wildintel-tools config show
```

We can find a detailed description of each configuration option in [configuración section](#⚙️-configuration).

### 📤 Step 2: Upload a collection

Once your configuration is ready, you can upload a collection from Trapper to Zooniverse. First, list available Trapper
collections:

```
trapper-zooniverse collections 
```

Then upload a specific collection by specifying its collection ID. 

```
trapper-zooniverse upload-collection 123
```

Optionally, you can also provide a name for the subject set that will be created in Zooniverse to store Trapper's images.

```
trapper-zooniverse upload-collection 123 subjetname_2123345
```

At the end of the image upload process, a report will be generated, which you can view by running:

```
trapper-zooniverse reports info
``` 

To see all reports that have been generated, run:

```
trapper-zooniverse reports list
```

During the image upload process to Zooniverse, a Zooniverse subject set will be created. You can view all subject sets 
created in your Zooniverse project by running:

```
trapper-zooniverse subjectsets
```

In this list, you can locate the created subject set and view the subjects (images) that were uploaded
by running:

```
trapper-zooniverse subjects 123
```

### Step 3: 📤 Publish Zooniverse Classifications to Trapper

Once all the Trapper images have been uploaded and linked to a Zooniverse subject set, the Zooniverse project administrator 
will need to attach that subject set to a workflow so the images (subjects) can be classified. 

After all subjects in a subject set have been retired (i.e., a consensus has been reached in the classifications), these 
classifications can be imported into Trapper. 

First, identify the subject set whose classifications you want to publish to Trapper.

```
trapper-zooniverse subjectsets
```

Second, identify which Trapper collection contains the images that were classified in this subject set. This ensures that 
the imported classifications are correctly associated with the original images.

```
trapper-zooniverse collections
```

Then, run the command to download and publish the classifications to Trapper:

```
trapper-zooniverse annotations-upload collection_12 sunject12 
```
The result of this execution will be a CSV file that can be imported directly into Trapper.

As was the case with the image upload process, a report will be generated at the end, and we can review its contents:

```
trapper-zooniverse reports info
``` 

## Other uses and deployment scenarios

In addition to the steps described in Quick Start, `trapper-zooniverse` can be used in several additional practical scenarios.

### Downloading Zooniverse images

The helper `dl_ss` downloads locally all images for a Zooniverse subject set. It is intended to fetch every subject in a
subject set and save files in a directory together with a small manifest that maps `subject_id → filename`.

Typical usage:

```bash
trapper-zooniverse helpers dl_ss  456 --output ./zoo-images 
```
What it does (summary):
* Downloads media associated with each subjectset specified
* Creates the output directory if it does not exist (--output, default: ./zoo-images).
* Saves each subject media file in the same `--output` directory  using the pattern: `subject_<subject_id>_<filename>.<ext>`
 
To obtain the ID of a subject set, you can run:

```bash
trapper-zooniverse helpers ss
``` 

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
## 📝 License

This project is licensed under the GNU General Public License v3.0 or later - see the LICENSE file for details.

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License
as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

## 🏛️ Funding

This work is part of the [WildINTEL project](https://wildintel.eu/), funded by the Biodiversa+ Joint Research Call 2022-2023 “Improved
transnational monitoring of biodiversity and ecosystem change for science and society (BiodivMon)”. Biodiversa+ is the 
European co-funded biodiversity partnership supporting excellent research on biodiversity with an impact for policy and
society. Biodiversa+ is part of the European Biodiversity Strategy for 2030 that aims to put Europe’s biodiversity on a
path to recovery by 2030 and is co-funded by the European Commission. 