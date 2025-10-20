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

Clone this repository and move into its directory:

```bash
git clone https://github.com/ijfvianauhu/trapper-zooniverse.git
cd trapper-zooniverse
```
Create a virtual environment, its dependencies and compile translation files:

```python
poetry install
poetry run compile-mo
```

Now you can run all commands within this isolated environment.
```
poetry shell
```

## ⚙️ Configuration

The client relies on a configuration file that stores login credentials, runtime parameters, and upload settings.

A sample default configuration might look like this:

```
[login]
trapper_username=myuser",
trapper_password=mypassword",
trapper_url=https://wildintel-trap.uhu.es",
trapper_access_token=my_secret_token",
zooniverse_project_id=your_project_id",
zooniverse_username=your_username",
zooniverse_password=your_password",

[logger]
loglevel="INFO",
logfilename": "app.log",
[i18n]
lang=en
locale_dir=/opt/trapper-zooniverse/locales
[upload_collection]
n_images_seq=5,              
max_interval=120,            
attempts=5,                  
delay=15,                    
max_attempts_per_subject=5,  
delay_seconds_per_subject=30 

[download_classifications]
```
#### 🔐 [login]

| Variable                | Description                                                                           |
| ----------------------- | ------------------------------------------------------------------------------------- |
| `trapper_username`      | Username used to log into WildINTEL-Trap.                                             |
| `trapper_password`      | Password for the Trapper user account.                                                |
| `trapper_url`           | Base URL of the WildINTEL-Trap instance.                                              |
| `trapper_access_token`  | API token used for authenticated access (optional if username/password are provided). |
| `zooniverse_project_id` | Zooniverse project ID where images will be uploaded.                                  |
| `zooniverse_username`   | Username for the Zooniverse account.                                                  |
| `zooniverse_password`   | Password for the Zooniverse account.                                                  |

#### 🧾 [logger]

| Variable      | Description                                                     |
| ------------- | --------------------------------------------------------------- |
| `loglevel`    | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`).            |
| `logfilename` | Path or name of the log file where client activity is recorded. |


#### 🌐 [i18n]

| Variable     | Description                                                       |
| ------------ | ----------------------------------------------------------------- |
| `lang`       | Interface language (e.g., `en`, `es`).                            |
| `locale_dir` | Path to the directory containing translation files (`.mo`/`.po`). |

#### 📤 [upload_collection]

| Variable                    | Description                                                                     |
| --------------------------- | ------------------------------------------------------------------------------- |
| `n_images_seq`              | Number of consecutive images per sequence uploaded as a single subject.         |
| `max_interval`              | Maximum allowed time interval (in seconds) between images in the same sequence. |
| `attempts`                  | Number of retry attempts when uploading fails.                                  |
| `delay`                     | Delay (in seconds) between retry attempts.                                      |
| `max_attempts_per_subject`  | Maximum number of upload attempts per subject before skipping it.               |
| `delay_seconds_per_subject` | Delay (in seconds) between subject uploads to prevent API overload.             |

### View current configuration

To inspect the current configuration, use the command:

```
trapper-zooniverse config
```

### Modify configuration interactively

You can update any configuration value directly from the command line using:
``` 
trapper-zooniverse config-set <section> <key> <value>
```
For example:

```
# Change the number of upload attempts
trapper-zooniverse config-set upload_collection upload_collection.attempts 10

# Update the Zooniverse project ID
trapper-zooniverse config-set login login.zooniverse_project_id 45678

# Switch interface language to Spanish
trapper-zooniverse config-set i18n.language es
```

## ⚡ Quick Start

Once you’ve installed [Trapper-Zooniverse](https://github.com/ijfvianauhu/trapper-zooniverse), you can start using it 
right away from the command line. Here’s what a typical first session looks like from a user’s perspective 

### 📋 Prerequisites

Before uploading images from Trapper to Zooniverse, you must first:

* Create a classification project.
* Assign a classifier to this project, where you define the list of species expected to appear in the Zooniverse annotations.
If desired, you can also add additional attributes or define your own custom ones.
* Once the project has been created, assign to it the collection containing the images you want to upload to Zooniverse.
* Run an AI model (for example, MegaDetector) to identify whether there are humans in the images.
* Review the results and approve them.

### ✅ Check your configuration

Before uploading or downloading anything, it’s a good idea to review your configuration file.

```
trapper-zooniverse config
```

### 📤 Upload a collection

Once your configuration is ready, you can upload a collection to Zooniverse. First, list available Trapper collections:

```
trapper-zooniverse collections 
```

Then upload a specific collection by specifying its collection ID. 

```
trapper-zooniverse upload-collection 123
```

Optionally, you can also provide a name for the subject set that will be created in Zooniverse.
```
trapper-zooniverse upload-collection 123 subjetname_2123345
```

###  📄 Review upload reports
At the end of the image upload process, a report will be generated, which you can view by running:

```
trapper-zooniverse collections-upload-report
``` 

To see all reports that have been generated, run:

```
trapper-zooniverse collections-upload-reports
```

To display the details of the latest one:

```
trapper-zooniverse collections-upload-report upload_report_47_33_20251020_124119.yaml
``` 

### 🔍 Retrieve Subject Sets and Subjects

During the image upload process to Zooniverse, a subject set was created. You can view all subject sets created in your 
Zooniverse project by running:

```
trapper-zooniverse subjectsets
```

In this list, you can locate the created subject set and view the subjects (images) that were uploaded
by running:

```
trapper-zooniverse subjects 123
```

### 📤 Publish Zooniverse Classifications to Trapper

After all subjects in a subject set have been retired (i.e., a consensus has been reached in the classifications), these 
classifications can be imported into Trapper. 

First, identify the subject set whose classifications you want to publish to Trapper.

```
trapper-zooniverse subjectsets
```

Second, identify which Trapper collection contains the images that were classified in this subject set. This ensures that the 
imported classifications are correctly associated with the original images.

```
trapper-zooniverse collections
```

Once the subject set is located and all subjects are retired, and the Trapper collection is identified, you can import the classifications into your Trapper project.
Then, run the command to download and publish the classifications to Trapper:

```
trapper-zooniverse annotations-upload collection_12 sunject12 
```
The result of this execution will be a CSV file that can be imported directly into Trapper.
Additionally, a report will be generated, which you can view by running:

```
trapper-zooniverse annotations-upload-report
``` 

To see all reports that have been generated, run:

```
trapper-zooniverse annotations-upload-reports
```

To display the details of one of them:

```
trapper-zooniverse annotations-upload-report upload_annotations_report_47_33_20251020_124119.yaml
```

## 🏛️ Funding

This work is part of the [WildINTEL project](https://wildintel.eu/), funded by the Biodiversa+ Joint Research Call 2022-2023 “Improved
transnational monitoring of biodiversity and ecosystem change for science and society (BiodivMon)”. Biodiversa+ is the 
European co-funded biodiversity partnership supporting excellent research on biodiversity with an impact for policy and
society. Biodiversa+ is part of the European Biodiversity Strategy for 2030 that aims to put Europe’s biodiversity on a
path to recovery by 2030 and is co-funded by the European Commission. 