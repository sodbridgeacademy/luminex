from rest_framework import generics, viewsets, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Sum
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.forms import PasswordResetForm
from .models import Organization, Assessment, Question, AssessmentSession, CandidateResponse
from .serializers import (
    RegisterSerializer, 
    UserProfileSerializer, 
    OrganizationSerializer,
    OrgRegisterSerializer,
    UserListSerializer,
    AssessmentSerializer,
    QuestionSerializer,
    StartTestSerializer, 
   # NextQuestionSerializer,
    QuestionSessionSerializer,
    ResultReviewSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    SubmitAnswerSerializer,
    CompleteTestSerializer
)
import random

User = get_user_model()


# ====================== AUTH ======================
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer


class ProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user

    def perform_update(self, serializer):
        # Handle profile picture upload
        serializer.save()
        return Response(serializer.data)


# ================= RESET PASSWORD ==============================
class ForgotPasswordView(generics.GenericAPIView):
    serializer_class = ForgotPasswordSerializer

    def post(self, request):

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        form = PasswordResetForm(
            {"email": serializer.validated_data["email"]}
        )

        if form.is_valid():
            form.save(
                request=request,
                use_https=request.is_secure(),
                email_template_name="registration/password_reset_email.html",
            )

        return Response(
            {"message": "Password reset email sent."},
            status=status.HTTP_200_OK,
        )


class ResetPasswordView(generics.GenericAPIView):
    serializer_class = ResetPasswordSerializer

    def post(self, request):

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uid = serializer.validated_data["uid"]
        token = serializer.validated_data["token"]

        try:
            user = User.objects.get(
                pk=urlsafe_base64_decode(uid).decode()
            )
        except Exception:
            return Response(
                {"error": "Invalid reset link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not default_token_generator.check_token(user, token):
            return Response(
                {"error": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data["password"])
        user.save(update_fields=["password"])

        return Response(
            {"message": "Password reset successful."},
            status=status.HTTP_200_OK,
        )


# ====================== ORGANIZATIONS ======================
class OrgRegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = OrgRegisterSerializer


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users can only see their own organization
        if self.request.user.organization:
            return Organization.objects.filter(id=self.request.user.organization.id)
        return Organization.objects.none()


class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserListSerializer
    permission_classes = [AllowAny]



class OrganizationListView(generics.ListAPIView):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]


# ====================== ASSESSMENTS ======================
class AssessmentViewSet(viewsets.ModelViewSet):
    queryset = Assessment.objects.all()
    serializer_class = AssessmentSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user, 
            organization=self.request.user.organization
        )

    def get_queryset(self):
        # Users can only see assessments from their organization
        if self.request.user.organization:
            return Assessment.objects.filter(organization=self.request.user.organization)
        return Assessment.objects.none()


class QuestionViewSet(viewsets.ModelViewSet):
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Question.objects.filter(
            assessment__organization=self.request.user.organization
        )

        assessment_id = self.request.query_params.get("assessment")

        if assessment_id:
            queryset = queryset.filter(assessment_id=assessment_id)

        return queryset

    def perform_create(self, serializer):
        assessment = serializer.validated_data["assessment"]

        if assessment.organization != self.request.user.organization:
            raise PermissionDenied(
                "Cannot create questions for another organization."
            )

        serializer.save()


class StartTestView(generics.CreateAPIView):
    serializer_class = StartTestSerializer
    permission_classes = [IsAuthenticated]

    # Prevent duplicate session
    def perform_create(self, serializer):
        existing = AssessmentSession.objects.filter(
            candidate=self.request.user,
            assessment=serializer.validated_data["assessment"],
            status="in_progress"
        ).first()

        if existing:
            serializer.instance = existing
            return

        serializer.save(candidate=self.request.user)


class NextQuestionView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = QuestionSessionSerializer

    def get(self, request, session_id):
        try:
            session = get_object_or_404(AssessmentSession, id=session_id, candidate=request.user,)
            assessment = session.assessment

            used_ids = [q['question_id'] for q in session.sequence] if session.sequence else []

            available_questions = Question.objects.filter(assessment=assessment).exclude(id__in=used_ids)

            if not available_questions.exists():
                return Response({"message": "Test completed"}, status=200)

            # Placeholder question selection.
            # Adaptive algorithm will be implemented in Phase 2.

            # Simple adaptive logic
            if session.sequence:
                #last_q = Question.objects.get(id=session.sequence[-1]['question_id'])
                last_difficulty = session.sequence[-1]["difficulty"]
                #last_difficulty = last_q.difficulty
            else:
                last_difficulty = 'medium'

            if last_difficulty == 'easy':
                next_question = available_questions.order_by('difficulty').first()
            elif last_difficulty == 'hard':
                next_question = available_questions.order_by('-difficulty').first()
            else:
                next_question = available_questions.order_by('?').first()

            # Save to sequence
            sequence = session.sequence or []
            sequence.append({
                "question_id": next_question.id, 
                "difficulty": next_question.difficulty
            })
            session.current_question = next_question
            session.last_activity = timezone.now()
            session.sequence = sequence
            session.save(
                update_fields=[
                    "sequence",
                    "current_question",
                    "last_activity",
                ]
            )
         
            serializer = QuestionSessionSerializer(next_question)

            return Response(serializer.data)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SubmitAnswerView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SubmitAnswerSerializer

    @transaction.atomic
    def post(self, request, session_id):

        session = get_object_or_404(
            AssessmentSession,
            id=session_id,
            candidate=request.user,
        )

        if session.status != "in_progress":
            return Response(
                {"error": "Assessment already completed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        question_id = request.data.get("question_id")
        answer = request.data.get("answer")

        if not question_id or answer is None:
            return Response(
                {"error": "question_id and answer are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        question = get_object_or_404(
            Question,
            id=question_id,
            assessment=session.assessment,
        )

        # Candidate can only answer the current question
        if session.current_question != question:
            return Response(
                {"error": "Invalid current question."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response, created = CandidateResponse.objects.get_or_create(
            session=session,
            question=question,
            defaults={
                "candidate": request.user,
                "assessment": session.assessment,
                "answer": answer,
            },
        )

        if not created:
            response.answer = answer

        # Auto-score MCQs
        if question.question_type == "mcq":
            is_correct = (
                str(answer).strip().lower()
                == str(question.correct_answer).strip().lower()
            )
            response.is_correct = is_correct
            response.score = 1 if is_correct else 0

        response.save()

        return Response(
            {"status": "submitted"},
            status=status.HTTP_200_OK,
        )


class CompleteTestView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CompleteTestSerializer

    @transaction.atomic
    def post(self, request, session_id):

        session = get_object_or_404(
            AssessmentSession,
            id=session_id,
            candidate=request.user,
        )

        if session.status == "completed":
            return Response(
                {"message": "Test already completed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        responses = session.responses.all()

        total_questions = responses.count()

        total_score = (
            responses.aggregate(total=Sum("score"))["total"]
            or 0
        )

        final_score = (
            (total_score / total_questions) * 100
            if total_questions
            else 0
        )

        session.final_score = final_score
        session.completed_at = timezone.now()
        session.status = "completed"
        session.last_activity = timezone.now()

        session.save(
            update_fields=[
                "final_score",
                "completed_at",
                "status",
                "last_activity",
            ]
        )

        return Response(
            {
                "message": "Test completed successfully",
                "final_score": round(final_score, 2),
                "total_questions": total_questions,
                "correct_answers": int(total_score),
            },
            status=status.HTTP_200_OK,
        )



class ResultReviewView(generics.RetrieveUpdateAPIView):
    serializer_class = ResultReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        session = get_object_or_404(
            AssessmentSession,
            id=self.kwargs["session_id"],
        )

        if session.assessment.organization != self.request.user.organization:
            raise PermissionDenied(
                "You cannot review results from another organization."
            )

        review, created = ResultReview.objects.get_or_create(
            session=session,
            defaults={
                "reviewed_by": self.request.user,
                "final_score": session.final_score or 0,
            },
        )

        return review

    @transaction.atomic
    def perform_update(self, serializer):
        serializer.save(reviewed_by=self.request.user)
