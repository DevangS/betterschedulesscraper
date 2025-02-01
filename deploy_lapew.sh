#!/bin/bash

# Create SSH control socket directory if it doesn't exist
mkdir -p ~/.ssh/controlmasters

# Enable connection sharing for this host
ssh -o ControlMaster=auto \
    -o ControlPath=~/.ssh/controlmasters/%r@%h:%p \
    -o ControlPersist=10 \
    devang@lapew true

# Now use the same connection for both commands
scp -o ControlPath=~/.ssh/controlmasters/%r@%h:%p main.py devang@lapew:/home/devang/betterschedulescraper
ssh -o ControlPath=~/.ssh/controlmasters/%r@%h:%p devang@lapew "sudo systemctl restart betterschedulescraper.service && journalctl -fu betterschedulescraper.service"