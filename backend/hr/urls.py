from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("hr/leave-types", views.LeaveTypeViewSet, basename="hr-leave-type")
router.register("hr/leave", views.LeaveViewSet, basename="hr-leave")
router.register("hr/salaries", views.SalaryViewSet, basename="hr-salary")
router.register("hr/payroll/runs", views.RunViewSet, basename="hr-run")
router.register("hr/payroll/entries", views.EntryViewSet, basename="hr-entry")
router.register("hr/payslips", views.PayslipViewSet, basename="hr-payslip")

urlpatterns = [
    path("hr/attendance/mine/", views.AttendanceMineView.as_view()),
    path("hr/attendance/mine/export/", views.AttendanceMineExportView.as_view()),
    path("hr/attendance/", views.AttendanceReportView.as_view()),
    path("hr/attendance/export/", views.AttendanceReportExportView.as_view()),
    path("hr/people/", views.PeopleView.as_view()),
] + router.urls
