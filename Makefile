.PHONY: requirements sam-build sam-local-invoke sam-deploy sam-validate clean test

# Export dependencies from pyproject.toml for SAM build
# Filter out the local package (-e .) which SAM can't handle
requirements:
	uv export --no-dev --no-hashes | grep -v "^-e " > src/requirements.txt

# Validate SAM template
sam-validate:
	sam validate --lint

# Build SAM application
sam-build: requirements
	sam build

# Local invoke with test event (requires Docker)
sam-local-invoke: sam-build
	sam local invoke GuardianStreamFunction -e events/test-event-minimal.json

# Local invoke with happy path event
sam-local-invoke-happy: sam-build
	sam local invoke GuardianStreamFunction -e events/test-event-happy-path.json

# Deploy to AWS (first time - guided)
sam-deploy-guided: sam-build
	sam deploy --guided

# Deploy to AWS (subsequent deploys)
sam-deploy: sam-build
	sam deploy

# Run all tests
test:
	uv run pytest tests/ -v

# Run infrastructure tests only
test-infra:
	uv run pytest tests/infrastructure/ -v

# Clean build artifacts
clean:
	rm -rf .aws-sam/
	rm -f src/requirements.txt
	rm -f samconfig.toml
	rm -f response.json
