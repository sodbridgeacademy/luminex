from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django.conf import settings

# 1. Custom User Model
class User(AbstractUser):
    USER_TYPE_CHOICES = [
        ('admin', 'Admin'),
        ('recruiter', 'Recruiter'),
        ('candidate', 'Candidate'),
        ('teacher', 'Teacher'),
    ]
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='candidate')
    organization = models.ForeignKey('Organization', on_delete=models.SET_NULL, null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField(
        upload_to='profile_pics/', 
        blank=True, 
        null=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])]
    )
    # Optional: Add more profile fields
    bio = models.TextField(blank=True)
    email = models.EmailField(unique=True)

    def __str__(self):
        return f"{self.username} ({self.user_type})"


# 2. Organization
class Organization(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    address = models.TextField(blank=True)
    industry = models.CharField(max_length=200, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# 3. Assessment
class Assessment(models.Model):
    STATUS_CHOICES = [('draft', 'Draft'), ('published', 'Published'), ('archived', 'Archived')]
    
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assessments_created')
    
    duration_minutes = models.IntegerField(default=60)
    is_private = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    passing_score = models.FloatField(default=60.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


# 4. Question
class Question(models.Model):
    QUESTION_TYPE = [('mcq', 'Multiple Choice'), ('oeq', 'Open Ended')]
    DIFFICULTY = [('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')]

    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    question_type = models.CharField(max_length=10, choices=QUESTION_TYPE)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY, default='medium')
    topic = models.CharField(max_length=150, blank=True)
    
    correct_answer = models.TextField(blank=True, help_text="For MCQ only")
    rubric = models.JSONField(blank=True, null=True, help_text="For Open-Ended questions")

   # competencies = models.ManyToManyField(Competency, related_name="questions", blank=True)
    
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.text[:80]}..."


# 5. QuestionOption (for MCQ)
class QuestionOption(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text


# 6. Adaptive/Assessment Session
class AssessmentSession(models.Model):
    STATUS_CHOICES = [
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("abandoned", "Abandoned"),
    ]

    candidate = models.ForeignKey(User, on_delete=models.CASCADE, related_name="assessment_sessions")

    assessment = models.ForeignKey(
        "Assessment",
        on_delete=models.CASCADE,
        related_name="sessions"
    )

    # Session state
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="in_progress"
    )

    current_question = models.ForeignKey(
        "Question",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+"
    )

    sequence = models.JSONField(
        default=list,
        help_text="Questions served in order."
    )

    # Results
    final_score = models.FloatField(
        null=True,
        blank=True
    )

    adaptive_enabled = models.BooleanField(default=False)
    difficulty_history = models.JSONField(
    default=list)

    estimated_ability = models.FloatField(
    null=True,
    blank=True)

    # Timing
    started_at = models.DateTimeField(auto_now_add=True)

    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )
    attempt_number = models.PositiveIntegerField(default=1, null=True)
    time_spent_seconds = models.PositiveIntegerField(default=0)
    last_activity = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["candidate","assessment","attempt_number"],
                name="unique_attempt"
            )
        ]

    def __str__(self):
        return f"{self.candidate.username} - {self.assessment.title}"

# 7. CandidateResponse
class CandidateResponse(models.Model):
    candidate = models.ForeignKey(User, on_delete=models.CASCADE, related_name='responses')
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer = models.TextField(blank=True)
    score = models.FloatField(null=True, blank=True)
    session = models.ForeignKey(AssessmentSession, on_delete=models.CASCADE, related_name="responses")
    response_time_ms = models.PositiveIntegerField(null=True, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('session', 'question')


# 8. ProctorFlag
class ProctorFlag(models.Model):
    FLAG_TYPE = [
        ('tab_switch', 'Tab Switch'),
        ('face_missing', 'Face Missing'),
        ('multiple_faces', 'Multiple Faces'),
        ('copy_paste', 'Copy-Paste Attempt'),
        ('full_screen_exit', 'Full Screen Exit'),
        ('other', 'Other'),
    ]
    
    session = models.ForeignKey(AssessmentSession, on_delete=models.CASCADE, related_name='flags')
    #candidate = models.ForeignKey(User, on_delete=models.CASCADE)
    flag_type = models.CharField(max_length=50, choices=FLAG_TYPE)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device = models.CharField(max_length=255, blank=True)
    browser = models.CharField(max_length=100, blank=True)
    operating_system = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.flag_type} - {self.candidate}"


# 9. AssessmentInvitation
class AssessmentInvitation(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    email = models.EmailField()
    access_code = models.CharField(max_length=50, unique=True)
    expiry = models.DateTimeField()
    used = models.BooleanField(default=False)
    sent_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.email} -> {self.assessment.title}"


# 10. ResultReview (Admin overrides & notes)
class ResultReview(models.Model):
    #adaptive_session = models.OneToOneField(AdaptiveSession, on_delete=models.CASCADE)
    session = models.OneToOneField(AssessmentSession, on_delete=models.CASCADE, related_name="review")
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    final_score = models.FloatField()
    notes = models.TextField(blank=True)
    published = models.BooleanField(default=False)
    reviewed_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Review for session {self.session.id}"


# 11. Competency
class Competency(models.Model):
    CATEGORY_CHOICES = [
        ("technical", "Technical"),
        ("soft_skill", "Soft Skill"),
        ("cognitive", "Cognitive"),
        ("behavioral", "Behavioral"),
        ("language", "Language"),
        ("custom", "Custom"),
    ]

    name = models.CharField(max_length=200)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="competencies", null=True,blank=True,)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default="technical"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="unique_competency_per_org"
            )
        ]

    def __str__(self):
        return self.name

    
# 12. Question Competency
class QuestionCompetency(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="competency_links"
    )

    competency = models.ForeignKey(
        Competency,
        on_delete=models.CASCADE,
        related_name="question_links"
    )

    weight = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=1.00
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["question", "competency"],
                name="unique_competency_per_question"
            )
        ]

    def __str__(self):
        return f"{self.question.id} → {self.competency.name}"
