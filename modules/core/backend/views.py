from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from modules.common.backend.permissions import IsAdminRole
from modules.core.backend import serializers

User = get_user_model()


class LoginView(TokenObtainPairView):
    """Obtain a JWT access/refresh pair using an email and a password."""

    serializer_class = serializers.EmailTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class LogoutView(APIView):
    """Blacklist the supplied refresh token, ending the session server-side."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            raise ValidationError({"refresh": _("This field is required.")})
        try:
            RefreshToken(refresh).blacklist()
        except TokenError:
            # The token is already expired or blacklisted: nothing else to do.
            pass
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(APIView):
    """Read or update the profile of the currently authenticated user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(serializers.UserSerializer(request.user).data)

    def patch(self, request):
        serializer = serializers.UserSelfUpdateSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializers.UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    """Change the password of the currently authenticated user."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = serializers.ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": _("Password has been changed.")})


class UserViewSet(viewsets.ModelViewSet):
    """CRUD administration of users (administrators only)."""

    queryset = User.objects.all()
    permission_classes = [IsAuthenticated, IsAdminRole]
    filterset_fields = ["role", "is_active"]
    search_fields = ["email", "first_name", "last_name", "middle_name", "phone"]
    ordering_fields = ["email", "last_name", "first_name", "role", "date_joined"]
    ordering = ["last_name", "first_name"]

    def get_serializer_class(self):
        if self.action == "create":
            return serializers.UserCreateSerializer
        if self.action in ("update", "partial_update"):
            return serializers.UserUpdateSerializer
        return serializers.UserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            serializers.UserSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = serializers.UserUpdateSerializer(
            instance, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(serializers.UserSerializer(user).data)

    def destroy(self, request, *args, **kwargs):
        """Deactivate a user by default, or delete it permanently on request.

        Pass ``?permanent=true`` to remove the record from the database. The
        soft delete is the default so that cash operations stay auditable.
        """
        user = self.get_object()
        if user == request.user:
            raise ValidationError({"detail": _("You cannot delete your own account.")})

        permanent = request.query_params.get("permanent", "").lower() in {"1", "true", "yes"}
        if permanent:
            user.delete()
        else:
            user.is_active = False
            user.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        user = self.get_object()
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])
        return Response(serializers.UserSerializer(user).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        user = self.get_object()
        if user == request.user:
            raise ValidationError({"detail": _("You cannot deactivate your own account.")})
        if user.is_active:
            user.is_active = False
            user.save(update_fields=["is_active"])
        return Response(serializers.UserSerializer(user).data)
