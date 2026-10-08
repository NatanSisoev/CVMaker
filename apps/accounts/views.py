"""Account-related views. Phase 6 swaps this for allauth."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import CreateView
from django_ratelimit.decorators import ratelimit
from rest_framework.authtoken.models import Token

from .forms import DeleteAccountForm, ProfileForm, SignUpForm
from .gdpr import delete_account, export_user_data


class SignUpView(CreateView):
    form_class = SignUpForm
    success_url = reverse_lazy("login")
    template_name = "accounts/signup.html"


@method_decorator(ratelimit(key="user", rate="10/m", method="POST"), name="post")
class AccountSettingsView(LoginRequiredMixin, View):
    """Profile + password on one page. Each form posts its own ``action``.

    Successful saves redirect back (post/redirect/get) with a flash message;
    invalid input re-renders with the other form untouched.
    """

    template_name = "accounts/settings.html"

    def _render(self, request, profile_form=None, password_form=None, delete_form=None):
        return render(
            request,
            self.template_name,
            {
                "profile_form": profile_form or ProfileForm(instance=request.user),
                "password_form": password_form or PasswordChangeForm(request.user),
                "api_token": Token.objects.filter(user=request.user).first(),
                "delete_form": delete_form or DeleteAccountForm(request.user),
            },
        )

    def get(self, request):
        return self._render(request)

    def post(self, request):
        action = request.POST.get("action")
        if action == "profile":
            form = ProfileForm(request.POST, instance=request.user)
            if form.is_valid():
                form.save()
                messages.success(request, "Profile saved.")
                return redirect("profile")
            return self._render(request, profile_form=form)
        if action == "password":
            form = PasswordChangeForm(request.user, request.POST)
            if form.is_valid():
                user = form.save()
                update_session_auth_hash(request, user)  # stay logged in
                messages.success(request, "Password changed.")
                return redirect("profile")
            return self._render(request, password_form=form)
        if action == "token-create":
            # Regenerating invalidates the old key immediately.
            Token.objects.filter(user=request.user).delete()
            Token.objects.create(user=request.user)
            messages.success(request, "New API token created. The previous one no longer works.")
            return redirect("profile")
        if action == "delete-account":
            form = DeleteAccountForm(request.user, request.POST)
            if not form.is_valid():
                return self._render(request, delete_form=form)
            user = request.user
            logout(request)  # end the session before the row disappears
            delete_account(user)
            messages.success(request, "Your account and all of its data were deleted.")
            return redirect("homepage")
        if action == "token-revoke":
            Token.objects.filter(user=request.user).delete()
            messages.success(request, "API token revoked.")
            return redirect("profile")
        return self._render(request)


class ExportDataView(LoginRequiredMixin, View):
    """GDPR data export: everything you authored, as one JSON download."""

    def get(self, request):
        stamp = timezone.now().strftime("%Y-%m-%d")
        response = JsonResponse(
            export_user_data(request.user),
            encoder=DjangoJSONEncoder,
            json_dumps_params={"indent": 2, "ensure_ascii": False},
        )
        response["Content-Disposition"] = f'attachment; filename="cvmaker-export-{stamp}.json"'
        return response
