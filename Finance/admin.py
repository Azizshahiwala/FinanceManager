from django.contrib import admin
from .models import *

@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ('date', 'user', 'category', 'item_name', 'amount')
    list_filter = ('category', 'date', 'user')
    search_fields = ('item_name', 'description', 'user__username')
    date_hierarchy = 'date'
    ordering = ('-date',)

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('date', 'user', 'category', 'item_name', 'quantity', 'unit', 'amount')
    list_filter = ('category', 'date', 'user')
    search_fields = ('item_name', 'description', 'user__username')
    date_hierarchy = 'date'
    ordering = ('-date',)

# @admin.register(TransactionLogs)
# class TransactionLogsAdmin(admin.ModelAdmin):
#     list_display = ('date', 'user', 'type', 'amount', 'record')
#     list_filter = ('type', 'date', 'user')
#     search_fields = ('record', 'description', 'user__username')
#     date_hierarchy = 'date'

@admin.register(TransactionLogs)
class TransactionLogsAdmin(admin.ModelAdmin):
    list_display = ('date', 'user', 'type', 'amount', 'record')
    list_filter = ('type', 'date', 'user')
    search_fields = ('record', 'description', 'user__username')
    date_hierarchy = 'date'
    actions = ['delete_selected']

@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'limit_amount', 'month')
    list_filter = ('category', 'month', 'user')

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'currency', 'phone', 'streaming_data')
    list_filter = ('currency', 'streaming_data')
    search_fields = ('user__username', 'phone')

class AmountFilter(admin.SimpleListFilter):
    title = 'amount'
    parameter_name = 'amount_range'

    def lookups(self, request, model_admin):
        return [('low', 'Under ₹500'), ('mid', '₹500 - ₹5000'), ('high', 'Over ₹5000')]

    def queryset(self, request, queryset):
        if self.value() == 'low':
            return queryset.filter(amount__lt=500)
        if self.value() == 'mid':
            return queryset.filter(amount__gte=500, amount__lte=5000)
        if self.value() == 'high':
            return queryset.filter(amount__gt=5000)