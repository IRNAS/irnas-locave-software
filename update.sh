#!/bin/bash

git pull && npm run build --prefix flash-ui

sudo systemctl restart locave.service
