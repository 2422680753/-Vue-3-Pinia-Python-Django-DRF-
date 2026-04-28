from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import StudentProfile, TeacherProfile, UserLoginRecord

User = get_user_model()


class StudentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = ['grade', 'school', 'learning_goals', 'preferred_subjects']


class TeacherProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherProfile
        fields = ['title', 'department', 'expertise', 'teaching_experience', 'certifications']


class UserSerializer(serializers.ModelSerializer):
    student_profile = StudentProfileSerializer(required=False, allow_null=True)
    teacher_profile = TeacherProfileSerializer(required=False, allow_null=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone', 'real_name', 'student_id',
            'role', 'role_display', 'avatar', 'bio', 'full_name',
            'student_profile', 'teacher_profile',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['is_active', 'created_at', 'updated_at']
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def create(self, validated_data):
        student_profile_data = validated_data.pop('student_profile', None)
        teacher_profile_data = validated_data.pop('teacher_profile', None)
        
        password = validated_data.pop('password', None)
        user = User.objects.create(**validated_data)
        
        if password:
            user.set_password(password)
            user.save()
        
        if student_profile_data and user.is_student:
            StudentProfile.objects.create(user=user, **student_profile_data)
        
        if teacher_profile_data and user.is_teacher:
            TeacherProfile.objects.create(user=user, **teacher_profile_data)
        
        return user

    def update(self, instance, validated_data):
        student_profile_data = validated_data.pop('student_profile', None)
        teacher_profile_data = validated_data.pop('teacher_profile', None)
        
        password = validated_data.pop('password', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        instance.save()
        
        if student_profile_data and instance.is_student:
            profile, created = StudentProfile.objects.get_or_create(user=instance)
            for attr, value in student_profile_data.items():
                setattr(profile, attr, value)
            profile.save()
        
        if teacher_profile_data and instance.is_teacher:
            profile, created = TeacherProfile.objects.get_or_create(user=instance)
            for attr, value in teacher_profile_data.items():
                setattr(profile, attr, value)
            profile.save()
        
        return instance


class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'phone', 'password', 'password_confirm',
            'real_name', 'role'
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "两次密码不一致"})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        
        if user.is_student:
            StudentProfile.objects.create(user=user)
        elif user.is_teacher:
            TeacherProfile.objects.create(user=user)
        
        return user


class UserLoginRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserLoginRecord
        fields = ['id', 'login_time', 'ip_address', 'device_info', 'location', 'is_success', 'failure_reason']
        read_only_fields = fields


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
