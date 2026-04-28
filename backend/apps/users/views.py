from rest_framework import generics, permissions, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, get_user_model
from django.shortcuts import get_object_or_404
from .models import UserLoginRecord
from .serializers import (
    UserSerializer, UserRegisterSerializer, UserLoginRecordSerializer,
    UserLoginSerializer
)

User = get_user_model()


class IsOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser or request.user.role == 'admin':
            return True
        return obj == request.user


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)


class LoginView(generics.GenericAPIView):
    serializer_class = UserLoginSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        username = serializer.validated_data.get('username')
        password = serializer.validated_data.get('password')
        
        user = authenticate(username=username, password=password)
        
        if user is None:
            self._log_login_attempt(request, username, False, '用户名或密码错误')
            return Response(
                {'error': '用户名或密码错误'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.is_active:
            self._log_login_attempt(request, username, False, '账户已禁用')
            return Response(
                {'error': '账户已被禁用'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        self._log_login_attempt(request, username, True)
        
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })

    def _log_login_attempt(self, request, username, success, reason=None):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return
        
        UserLoginRecord.objects.create(
            user=user,
            ip_address=request.META.get('REMOTE_ADDR', 'unknown'),
            device_info=request.META.get('HTTP_USER_AGENT', 'unknown'),
            is_success=success,
            failure_reason=reason
        )


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == 'admin':
            return User.objects.all()
        elif user.role == 'teacher':
            return User.objects.filter(role='student')
        return User.objects.filter(id=user.id)

    @action(detail=False, methods=['get'], url_path='me')
    def get_current_user(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['put', 'patch'], url_path='update-me')
    def update_current_user(self, request):
        partial = request.method == 'PATCH'
        serializer = self.get_serializer(
            request.user,
            data=request.data,
            partial=partial
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='login-records')
    def get_login_records(self, request):
        records = UserLoginRecord.objects.filter(user=request.user)[:20]
        serializer = UserLoginRecordSerializer(records, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        if not request.user.is_superuser and request.user.role != 'admin':
            return Response(
                {'error': '没有权限执行此操作'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        user = self.get_object()
        if user == request.user:
            return Response(
                {'error': '不能禁用自己的账户'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.is_active = not user.is_active
        user.save()
        
        return Response({
            'message': f'用户状态已更新为{"激活" if user.is_active else "禁用"}',
            'is_active': user.is_active
        })


class LogoutView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            return Response(
                {'message': '退出登录成功'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': '退出登录失败'},
                status=status.HTTP_400_BAD_REQUEST
            )


class ChangePasswordView(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def update(self, request, *args, **kwargs):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')

        if not user.check_password(old_password):
            return Response(
                {'error': '原密码不正确'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if new_password != confirm_password:
            return Response(
                {'error': '两次新密码不一致'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save()

        return Response(
            {'message': '密码修改成功'},
            status=status.HTTP_200_OK
        )
