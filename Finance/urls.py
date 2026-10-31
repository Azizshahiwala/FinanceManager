from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path('', views.homePage, name='homePage'),
    path('error/', views.errorPage, name='errorPage'),
    path('login/', views.login, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('transaction/', views.transaction, name='transaction'),
    # path('update-budget/', views.updateBudget, name='updateBudget'),
    path('expense-add/', views.expenseAdd, name='expenseAdd'),
    path('income-add/', views.incomeAdd, name='incomeAdd'),
    
    path('export/live-link/', views.generateLiveLink, name='generateLiveLink'),
    path('export/live-link/data/', views.liveTransactionData, name='liveTransactionData'),
    path('export/live-link/revoke/', views.revokeLiveLink, name='revokeLiveLink'),
    
    path('export-area/', views.exportData, name='exportArea'),
    
    path('reports/', views.reportsHome, name='reportsHome'),
    path('reports/preview/', views.reportPreview, name='reportPreview'),
    path('reports/pdf/', views.reportPdf, name='reportPdf'),
]