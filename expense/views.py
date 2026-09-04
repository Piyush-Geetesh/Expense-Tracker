from django.shortcuts import render, redirect
from django.db.models import Sum
from .models import Expense, Salary


def home(request):

    if request.method == 'POST':
        amount = request.POST.get('amount')
        description = request.POST.get('description')

        if amount and description:
            Expense.objects.create(
                amount=amount,
                description=description
            )

        return redirect('home')

    # Get all expenses
    expenses = Expense.objects.all().order_by('-created_at')

    # Get latest salary
    salary = Salary.objects.order_by('-credited_at').first()

    # Calculate total expenses
    total_expenses = Expense.objects.aggregate(
        total=Sum('amount')
    )['total'] or 0

    # Calculate remaining balance
    if salary:
        balance = salary.amount - total_expenses
    else:
        balance = 0

    print("SALARY =", salary)
    print("TOTAL EXPENSES =", total_expenses)
    print("BALANCE =", balance)

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