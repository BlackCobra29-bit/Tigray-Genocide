from django.core.mail.backends.smtp import EmailBackend


class DatabasePasswordEmailBackend(EmailBackend):
    """Load the SMTP password after Django's app registry is ready."""

    def open(self):
        if not self.password:
            from .models import Webmail_password_manager

            password_record = Webmail_password_manager.objects.first()
            if password_record is not None:
                self.password = password_record.password

        return super().open()
