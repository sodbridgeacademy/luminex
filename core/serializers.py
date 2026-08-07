from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Organization, User, Assessment, QuestionOption, Question, AssessmentSession, ResultReview
from django.db import transaction
from django.utils.text import slugify

User = get_user_model()

# ====================== AUTH ======================
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "password", "confirm_password", "user_type",]

    def validate(self, data):
        if not data.get("first_name"):
            raise serializers.ValidationError({
                "first_name": "This field is required."
            })

        if not data.get("last_name"):
            raise serializers.ValidationError({
                "last_name": "This field is required."
            })

        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })

        return data

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        validated_data["user_type"] = "candidate"

        return User.objects.create_user(**validated_data)


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                 'user_type', 'profile_picture', 'bio', 'organization']
        read_only_fields = ['id', 'username', 'email', 'user_type', 'organization']


# ====================== ORGANIZATION ======================
class OrgRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    organization_name = serializers.CharField(write_only=True)
    organization_industry = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "confirm_password",
            "first_name",
            "last_name",
            "organization_name",
            "organization_industry",
        ]

    def validate(self, data):

        if not data.get("first_name"):
            raise serializers.ValidationError({
                "first_name": "This field is required."
            })

        if not data.get("last_name"):
            raise serializers.ValidationError({
                "last_name": "This field is required."
            })

        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })

        return data

    def create(self, validated_data):

        validated_data.pop("confirm_password")

        org_name = validated_data.pop("organization_name")
        org_industry = validated_data.pop("organization_industry")

        organization = Organization.objects.create(
            name=org_name,
            industry=org_industry,
            #slug=org_name.lower().replace(" ", "-").replace(".", ""),
            slug = slugify(org_name)
        )

        user = User.objects.create_user(**validated_data)

        user.organization = organization
        user.user_type = "admin"
        user.save()

        return user


# Org Serializer
class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'slug', 'address', 'industry', 'created_at']
        read_only_fields = ['slug', 'created_at']


# Add this serializer
class UserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                 'user_type', 'organization', 'profile_picture']
        read_only_fields = ['id']


# ====================== PASSWORD RESETS ======================
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "No account exists with this email."
            )
        return value

class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()

    password = serializers.CharField(
        write_only=True,
        min_length=8,
    )

    confirm_password = serializers.CharField(
        write_only=True,
    )

    def validate(self, attrs):

        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })

        return attrs


# ====================== ASSESSMENTS ======================
class AssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assessment
        fields = ['id', 'title', 'description', 'duration_minutes', 
                 'is_private', 'status', 'passing_score', 'created_at', 'created_by']
        read_only_fields = ['created_by', 'status', 'created_at']
     
# ====================== For Orgs ======================
class QuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ['id', 'text', 'is_correct']   


# ====================== QUESTIONS ======================
class QuestionSerializer(serializers.ModelSerializer):
    options = QuestionOptionSerializer(many=True, required=False)

    class Meta:
        model = Question
        fields = [
            "id",
            "assessment",
            "text",
            "question_type",
            "difficulty",
            "topic",
            "rubric",
            "order",
            "options",
        ]
        read_only_fields = ["correct_answer"]

    def validate(self, data):
        question_type = data.get(
            "question_type",
            getattr(self.instance, "question_type", None)
        )

        options = data.get("options")
        rubric = data.get(
            "rubric",
            getattr(self.instance, "rubric", None)
        )

        # ==========================
        # MCQ Validation
        # ==========================
        if question_type == "mcq":

            # New MCQ must include options
            if self.instance is None and not options:
                raise serializers.ValidationError({
                    "options": "MCQ questions require at least two options."
                })

            # Validate supplied options
            if options is not None:

                if len(options) < 2:
                    raise serializers.ValidationError({
                        "options": "MCQ questions require at least two options."
                    })

                correct_options = [
                    option
                    for option in options
                    if option.get("is_correct", False)
                ]

                if len(correct_options) != 1:
                    raise serializers.ValidationError({
                        "options": "Exactly one option must be marked as correct."
                    })

                # Automatically derive the correct answer
                data["correct_answer"] = correct_options[0]["text"]
                data["rubric"] = None

        # ==========================
        # Open-ended Validation
        # ==========================
        elif question_type == "oeq":

            if options:
                raise serializers.ValidationError({
                    "options": "Open-ended questions cannot have options."
                })

            if not rubric:
                raise serializers.ValidationError({
                    "rubric": "Open-ended questions require a grading rubric."
                })

            # OEQs never use correct_answer
            data["correct_answer"] = ""

        # Ensures a question data type is made
        else:
            raise serializers.ValidationError({
                "question_type": "Invalid question type."
            })

        return data

    @transaction.atomic
    def create(self, validated_data):
        options_data = validated_data.pop("options", [])

        question = Question.objects.create(**validated_data)

        if options_data:
            QuestionOption.objects.bulk_create([
                QuestionOption(question=question, **option)
                for option in options_data
            ])

        return question

    @transaction.atomic
    def update(self, instance, validated_data):
        validated_data.pop("assessment", None)
        options_data = validated_data.pop("options", None)


        # Update normal fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # ==========================
        # Keep data consistent
        # ==========================

        if instance.question_type == "mcq":
            # MCQs don't use rubrics
            instance.rubric = None

        elif instance.question_type == "oeq":
            # OEQs don't use answers/options
            instance.correct_answer = ""
            instance.options.all().delete()

        # Update options if supplied
        if options_data is not None:

            instance.options.all().delete()

            QuestionOption.objects.bulk_create([
                QuestionOption(question=instance, **option)
                for option in options_data
            ])



            if instance.question_type == "mcq":
                correct_option = next(
                    option for option in options_data
                    if option.get("is_correct")
                )

                instance.correct_answer = correct_option["text"]

        instance.save(
            update_fields=[
                "text",
                "question_type",
                "difficulty",
                "topic",
                "rubric",
                "order",
                "correct_answer",
            ]
        )

        return instance


# ====================== For Candidates ======================
class QuestionSessionSerializer(serializers.ModelSerializer):
    options = QuestionOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            "id",
            "text",
            "question_type",
            "topic",
            "options",
        ]


# ====================== ADAPTIVE TESTS ======================
class StartTestSerializer(serializers.ModelSerializer):

    class Meta:
        model = AssessmentSession
        fields = [
            "id", "assessment", "candidate", "attempt_number", "status", "started_at",]
        read_only_fields = ["candidate", "status", "started_at", "attempt_number",]


# ====================== RESULTS REVIEW ======================
class ResultReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResultReview
        fields = [
            "id",
            "session",
            "final_score",
            "notes",
            "published",
            "reviewed_at",
        ]
        read_only_fields = [
            "reviewed_by",
            "reviewed_at",
            "session",
        ]


class SubmitAnswerSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    answer = serializers.CharField()


class CompleteTestSerializer(serializers.Serializer):
    pass
    
    '''
    POS - Jolayemi Seun Odogbolu, First bank, 3083307161, contact: 07031963006 

    '''


