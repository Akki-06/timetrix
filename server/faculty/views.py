from rest_framework import viewsets
from .models import *
from .serializers import *

class FacultyViewSet(viewsets.ModelViewSet):
    queryset = Faculty.objects.all()
    serializer_class = FacultySerializer
    
class TeacherAvailabilityViewSet(viewsets.ModelViewSet):
    queryset = TeacherAvailability.objects.all()
    serializer_class = TeacherAvailabilitySerializer
    
class FacultySubjectEligibilityViewSet(viewsets.ModelViewSet):
    queryset = FacultySubjectEligibility.objects.all()
    serializer_class = FacultySubjectEligibilitySerializer
    
