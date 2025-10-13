# trapper_zooniverse
A bridge for integrating Trapper with Zooniverse projects 

Trapper-Zooniverse is a Python client that allows you to upload image collections to Zooniverse and download 
classification results from wildlife monitoring projects such as those within the WildINTEL initiative.

It provides seamless integration between the Trapper system and Zooniverse, automatically handling:

* Image grouping by deploymentID and timestamp,
* Robust multi-attempt uploads with retries and exponential backoff,
* Detailed YAML reports (UploadReport) of each upload operation.

## Installation

Clone the repository and move into its directory:

```bash
git clone https://github.com/ijfvianauhu/trapper-zooniverse.git
cd trapper-zooniverse
```
Create a virtual environment and its dependencies:
```python
poetry install
```

## Configuration

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
lang=en
loglevel="INFO",
logfilename": "app.log",
[upload_collection]
n_images_seq=5,              
max_interval=120,            
attempts=5,                  
delay=15,                    
max_attempts_per_subject=5,  
delay_seconds_per_subject=30 
[download_classifications]
```

### View current configuration

To inspect the current configuration, use the command:

```
trapper-zooniverse show-config
```

### Modify configuration interactively

You can update any configuration value directly from the command line using:
``` 
trapper-zooniverse set-config <section> <key> <value>
```
For example:

```
# Change the number of upload attempts
trapper-zooniverse set-config upload_collection attempts 10

# Update the Zooniverse project ID
trapper-zooniverse set-config login zooniverse_project_id 45678

# Switch interface language to Spanish
trapper-zooniverse set-config logger lang es
```

## Quick Start

Once you’ve installed Trapper-Zooniverse, you can start using it right away from the command line.
Here’s what a typical first session looks like from a user’s perspective 

### Check your configuration

Before uploading or downloading anything, it’s a good idea to review your configuration file.

```
trapper-zooniverse show-config
```

### Upload a collection

Once your configuration is ready, you can upload a collection to Zooniverse. First, list available collections:

```
trapper-zooniverse collections 
```

Then upload a specific collection by its ID and give it a name:
```
trapper-zooniverse upload-collection 123
```

### Review upload reports

To see all upload reports you’ve generated:

```
trapper-zooniverse list-upload-reports
```

To display the details of the latest one:

```
trapper-zooniverse show-upload-report
``` 

### Retrieve Subject Sets and Subjects

You can also retrieve all subject sets created in Zooniverse project:

```
trapper-zooniverse subjectsets
```
Also, you can list all subjects linked to a subjectset:

```
trapper-zooniverse subjects 123
```