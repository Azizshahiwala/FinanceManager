from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    username = models.CharField(max_length=255, blank=True, default='')
    currency = models.CharField(max_length=10, default='INR')
    phone = models.CharField(max_length=15, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    streaming_data = models.BooleanField(default=False, blank=False)
    streaming_token_version = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        if not self.username and self.user_id:
            self.username = self.user.username
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username or self.user.username

class TransactionLogs(models.Model):
    '''
    This class is for displaying written summary in html, data
    is received from income and expense...

    graphs and statistical info is directly fetched from income,expense
    table.
    '''
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=100)
    source_id = models.PositiveIntegerField(null=True, blank=True)
    date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    record = models.CharField(max_length=255, blank=True, null=True) 
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'type', 'source_id']),
        ]

    def __str__(self):
        record= f'''
        {self.date} | Username: {self.user.username}, Transaction type: {self.type}, Amount: {self.amount}, Record:{self.record}, Description:{self.description}
        '''
        return record

class Budget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.CharField(max_length=50, default='Other')
    limit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    month = models.DateField()  

    def __str__(self):
        return f"{self.user.username} - {self.category} - {self.month.strftime('%b %Y')}"

class Income(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=100)
    date = models.DateField()
    category = models.CharField(max_length=100, default='Other')
    item_name = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2) 
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        record= f'''
        {self.date} | Username: {self.user.username}, Transaction type: {self.type}. | Info: {self.item_name}, Amount: {self.amount}.
            '''
        return record
    
class Expense(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=100)
    date = models.DateField()
    category = models.CharField(max_length=100, default='Other')
    item_name = models.CharField(max_length=255, blank=True, null=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    unit = models.CharField(max_length=50, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        record= f'''
        {self.date} | Username: {self.user.username}, Transaction type: {self.type}. | Item: {self.item_name}, Qtd: {self.quantity}, Unit: {self.unit}.
            '''
        return record
