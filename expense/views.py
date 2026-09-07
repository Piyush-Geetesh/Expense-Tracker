from django.shortcuts import render, redirect
from django.db.models import Sum
from .models import Expense, Salary


def home(request):

    if request.method == 'POST':

        # Salary form submitted
        if 'salary_submit' in request.POST:
            salary_amount = request.POST.get('salary_amount')

            if salary_amount:
                Salary.objects.create(
                    amount=salary_amount
                )

            return redirect('home')

        # Expense form submitted
        if 'expense_submit' in request.POST:
            amount = request.POST.get('amount')
            description = request.POST.get('description')

            if amount and description:
                Expense.objects.create(
                    amount=amount,
                    description=description
                )

            return redirect('home')

    expenses = Expense.objects.all().order_by('-created_at')

    salary = Salary.objects.order_by(
        '-credited_at'
    ).first()

    total_expenses = Expense.objects.aggregate(
        total=Sum('amount')
    )['total'] or 0

    if salary:
        balance = salary.amount - total_expenses
    else:
        balance = 0

    return render(
        request,
        'expense/home.html',
        {
            'expenses': expenses,
            'salary': salary,
            'total_expenses': total_expenses,
            'balance': balance,
        }
    )
def delete_expense(request, expense_id):
    if request.method == 'POST':
        expense = Expense.objects.get(id=expense_id)
        expense.delete()

    return redirect('home')