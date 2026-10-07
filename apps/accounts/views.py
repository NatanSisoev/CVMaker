"""Account-related views. Phase 6 swaps this for allauth."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView

from .forms import ProfileForm, SignUpForm


class SignUpView(CreateView):
    form_class = SignUpForm
    success_url = reverse_lazy("login")
    template_name = "accounts/signup.html"


class AccountSettingsView(LoginRequiredMixin, View):
    """Profile + password on one page. Each form posts its own ``action``.

    Successful saves redirect back (post/redirect/get) with a flash message;
    invalid input re-renders with the other form untouched.
    """

    template_name = "accounts/settings.html"

    def _render(self, request, profile_form=None, password_form=None):
        return render(
            request,
            self.template_name,
            {
                "profile_form": profile_form or ProfileForm(instance=request.user),
                "password_form": password_form or PasswordChangeForm(request.user),
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
        return self._render(request)
