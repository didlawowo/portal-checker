#!/bin/bash
set -e

echo "🔍 Copying pre-installed SpaCy models to shared volume..."

# Create target directory
mkdir -p /shared/spacy_models

# Copy SpaCy models from site-packages to shared volume
SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])")
echo "📦 SpaCy models location: $SITE_PACKAGES"

# Copy models (already downloaded in image)
if [ -d "$SITE_PACKAGES/en_core_web_sm" ]; then
    echo "📋 Copying en_core_web_sm..."
    cp -r "$SITE_PACKAGES/en_core_web_sm" /shared/spacy_models/
fi

if [ -d "$SITE_PACKAGES/en_core_web_md" ]; then
    echo "📋 Copying en_core_web_md..."
    cp -r "$SITE_PACKAGES/en_core_web_md" /shared/spacy_models/
fi

# Create a marker file to indicate models are ready
touch /shared/spacy_models/.ready

echo "✅ SpaCy models copied successfully (no download needed)"
ls -la /shared/spacy_models/