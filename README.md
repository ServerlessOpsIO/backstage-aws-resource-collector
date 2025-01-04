# backstage / backstage-aws-resource-collector

Collect resources from AWS accounts


## New Project Getting Started
This repository was generated from a template intended to get a new API up and running quickly. This section will cover different aspects of the newly created project as well as areas that may need to be modified to meet the specific needs of a new project.


### Code
When starting a new project the first place to start with adapting the code to meet the needs of a new project is the [`src/common/common/model/.py`](src/common/common/model/.py) file. This file contains interfaces for data and DDB table items.

Start by modifying the dataclasses to match the shape of your data. Optionally you can choose to replace that interface with one from another module if you're working with a pre-existing data model. The existing interface definition was chosen simply to make the project work out of the box.

### Account Requirements
The account where ListAccounts runs must be a delegated admin account.