.PHONY: build-ApprovalProcessorFunction build-PortalApiFunction build-ApprovalReminderFunction build-ReportGeneratorFunction

# Shared build logic: copy only Lambda-relevant Python code + install deps
define lambda_build
	@echo "Building Lambda: $(1)"
	mkdir -p $(ARTIFACTS_DIR)/lambdas
	mkdir -p $(ARTIFACTS_DIR)/src/approval/services
	mkdir -p $(ARTIFACTS_DIR)/src/approval/templates
	mkdir -p $(ARTIFACTS_DIR)/src/db
	mkdir -p $(ARTIFACTS_DIR)/config/brands
	cp -r lambdas/ $(ARTIFACTS_DIR)/lambdas/
	cp -r src/approval/ $(ARTIFACTS_DIR)/src/approval/
	touch $(ARTIFACTS_DIR)/src/__init__.py
	cp src/db/__init__.py $(ARTIFACTS_DIR)/src/db/__init__.py
	cp src/db/models.py $(ARTIFACTS_DIR)/src/db/models.py
	cp src/db/admin_models.py $(ARTIFACTS_DIR)/src/db/admin_models.py
	cp -r config/ $(ARTIFACTS_DIR)/config/
	pip install -r requirements.txt -t $(ARTIFACTS_DIR)/ --cache-dir .pip-cache --platform manylinux2014_x86_64 --only-binary=:all: --implementation cp --python-version 3.13 --upgrade --quiet
endef

build-ApprovalProcessorFunction:
	$(call lambda_build,ApprovalProcessorFunction)

build-PortalApiFunction:
	$(call lambda_build,PortalApiFunction)

build-ApprovalReminderFunction:
	$(call lambda_build,ApprovalReminderFunction)

build-ReportGeneratorFunction:
	@echo "Building report_generator Lambda..."
	mkdir -p $(ARTIFACTS_DIR)/lambdas
	mkdir -p $(ARTIFACTS_DIR)/src/agents
	cp -r lambdas/ $(ARTIFACTS_DIR)/lambdas/
	cp -r src/agents/schemas.py $(ARTIFACTS_DIR)/src/agents/schemas.py
	touch $(ARTIFACTS_DIR)/src/__init__.py
	touch $(ARTIFACTS_DIR)/src/agents/__init__.py
	pip install -r requirements-report.txt -t $(ARTIFACTS_DIR)/ --cache-dir .pip-cache --platform manylinux2014_x86_64 --only-binary=:all: --implementation cp --python-version 3.13 --upgrade --quiet
