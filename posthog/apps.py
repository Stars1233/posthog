import os

import posthoganalytics
import structlog
from django.apps import AppConfig, apps
from django.conf import settings
from posthoganalytics.client import Client
from posthoganalytics.exception_capture import Integrations

from posthog.git import get_git_branch, get_git_commit_short
from posthog.settings import SELF_CAPTURE, SKIP_ASYNC_MIGRATIONS_SETUP
from posthog.tasks.tasks import sync_all_organization_available_product_features
from posthog.utils import get_machine_id, get_self_capture_api_token

logger = structlog.get_logger(__name__)


class PostHogConfig(AppConfig):
    name = "posthog"
    verbose_name = "PostHog"

    def ready(self):
        posthoganalytics.api_key = "sTMFPsFhdP1Ssg"
        posthoganalytics.personal_api_key = os.environ.get("POSTHOG_PERSONAL_API_KEY")
        posthoganalytics.poll_interval = 90
        posthoganalytics.enable_exception_autocapture = True
        posthoganalytics.exception_autocapture_integrations = [Integrations.Django]

        if settings.E2E_TESTING:
            posthoganalytics.api_key = "phc_ex7Mnvi4DqeB6xSQoXU1UVPzAmUIpiciRKQQXGGTYQO"
            posthoganalytics.personal_api_key = None
        elif settings.TEST or os.environ.get("OPT_OUT_CAPTURE", False):
            posthoganalytics.disabled = True
        elif settings.DEBUG:
            User = apps.get_model("posthog", "User")

            # log development server launch to posthog
            if os.getenv("RUN_MAIN") == "true":
                # Sync all organization.available_product_features once on launch, in case plans changed
                sync_all_organization_available_product_features()

                # NOTE: This has to be created as a separate client so that the "capture" call doesn't lock in the properties
                phcloud_client = Client(posthoganalytics.api_key)

                phcloud_client.capture(
                    get_machine_id(),
                    "development server launched",
                    {"git_rev": get_git_commit_short(), "git_branch": get_git_branch()},
                )

            try:
                user = User.objects.filter(last_login__isnull=False).order_by("-last_login").first()
            except:
                user = None

            local_api_key = get_self_capture_api_token(user)

            if SELF_CAPTURE and local_api_key:
                posthoganalytics.api_key = local_api_key
                posthoganalytics.host = settings.SITE_URL
            else:
                posthoganalytics.disabled = True

        # load feature flag definitions if not already loaded
        if not posthoganalytics.disabled and posthoganalytics.feature_flag_definitions() is None:
            posthoganalytics.load_feature_flags()

        from posthog.async_migrations.setup import setup_async_migrations

        if SKIP_ASYNC_MIGRATIONS_SETUP:
            logger.warning("Skipping async migrations setup. This is unsafe in production!")
        else:
            setup_async_migrations()
