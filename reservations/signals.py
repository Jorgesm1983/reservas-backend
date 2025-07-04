from django.dispatch import receiver
from django_rest_passwordreset.signals import reset_password_token_created
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, *args, **kwargs):
    context = {
        'current_user': reset_password_token.user,
        'reset_password_url': f"http://www.pistareserva.com/reset-password-confirm/?token={reset_password_token.key}"
    }
    html_content = render_to_string('emails/user_reset_password.html', context)
    text_content = strip_tags(html_content)

    subject = "Recupera tu contraseña"
    from_email = "info@pistareserva.com"
    to_email = [reset_password_token.user.email]

    msg = EmailMultiAlternatives(subject, text_content, from_email, to_email)
    msg.attach_alternative(html_content, "text/html")
    msg.send()
