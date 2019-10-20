from pynabapi import YnabClient
import os
import gspread
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

# Ynab
client = YnabClient(os.environ['YNAB_KEY'])
budget_id = os.environ['BUDGET_ID']

# Google
scope = ['https://www.googleapis.com/auth/spreadsheets']
sheets_credentials = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
gc = gspread.authorize(sheets_credentials)
sheet = gc.open_by_key(os.environ['GOOGLE_SHEET_ID'])
worksheet = sheet.sheet1


def main(event, context):
    transactions_by_cc = fetch_transaction_data_from_ynab()
    update_last_charge(transactions_by_cc)
    update_total_spend(transactions_by_cc)
    update_balance()


def update_balance():
    credit_card_ids = fetch_credit_card_account_ids()
    accounts = client.get_budget(summary=False).accounts
    credit_card_accounts = [account for account in accounts if account.id in credit_card_ids and not account.closed]
    column = worksheet.find("Balance").col
    for account in credit_card_accounts:
        credit_card_id = account.id
        balance = format_amount(account.cleared_balance)

        print("Updating balance for account " + credit_card_id + ": " + str(balance))
        row = worksheet.find(credit_card_id).row
        worksheet.update_cell(row, column, balance)


def update_last_charge(transactions_by_cc):
    column = worksheet.find("Last Charge").col
    for credit_card_id, transactions in transactions_by_cc.items():
        latest_charge = max(transactions, key=lambda x: x.date).date
        latest_charge_as_string = latest_charge.strftime("%d %b %Y")

        print("Updating card " + credit_card_id + " latest charge: " + latest_charge_as_string)
        row = worksheet.find(credit_card_id).row
        worksheet.update_cell(row, column, latest_charge_as_string)


def update_total_spend(transactions_by_cc):
    column = worksheet.find("Total Spend").col
    for credit_card_id, transactions in transactions_by_cc.items():
        total_spend = 0
        for transaction in transactions:
            if transaction.amount < 0 and not transaction.deleted and transaction.cleared == 'cleared':
                total_spend += transaction.amount
        total_spend = format_amount(total_spend)
        print("Updating card " + credit_card_id + " total spend: " + str(total_spend))

        row = worksheet.find(credit_card_id).row
        worksheet.update_cell(row, column, str(total_spend))


def fetch_credit_card_account_ids():
    budget = client.get_budget(summary=False, budget_id=budget_id)
    accounts = list(filter(lambda account: not account.closed and account.type == 'creditCard', budget.accounts))

    account_ids = {account.id for account in accounts}

    return account_ids


def fetch_transaction_data_from_ynab():
    credit_card_ids = fetch_credit_card_account_ids()
    transactions = client.get_transaction(budget_id=budget_id)
    credit_card_transactions = [transaction for transaction in transactions if transaction.account_id in credit_card_ids]
    credit_card_transactions = parse_all_dates(credit_card_transactions)

    result = {}
    for transaction in credit_card_transactions:
        account_id = transaction.account_id
        if account_id in result:
            result[account_id].append(transaction)
        else:
            result[account_id] = [transaction]

    return result


def parse_all_dates(transactions):
    for transaction in transactions:
        transaction.date = parse_date(transaction.date)

    return transactions


def parse_date(date_string):
    return datetime.strptime(date_string, '%Y-%m-%d')


def format_amount(amount):
    return round((amount * -1) / 1000, 2)
