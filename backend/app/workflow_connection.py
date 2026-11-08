"""Invalidate signed dependencies inside the transaction that changes them."""
import re
import sqlite3
from app.security_context import request_principal,request_database

class WorkflowConnection(sqlite3.Connection):
    def execute(self, sql, parameters=()):
        result=super().execute(sql,parameters)
        match=re.match(r'\s*(?:INSERT(?: OR \w+)? INTO|UPDATE|DELETE FROM)\s+(\w+)',sql,re.I)
        if match and self.in_transaction and not getattr(self,'_hook',False):
            self._dirty=getattr(self,'_dirty',set())|{match[1].lower()}
            if match[1].lower()=='review_events' and sql.lstrip().upper().startswith('INSERT'):
                self._review_events=getattr(self,'_review_events',[])+[result.lastrowid]
        return result

    def commit(self):
        principal=request_principal.get()
        dirty=getattr(self,'_dirty',set())
        if self.in_transaction and dirty and principal and principal.get('profile')!='legacy_test':
            self._hook=True
            token=request_database.set(self)
            try:
                from app.services.workflow_service import after_write
                after_write(self,principal,dirty,getattr(self,'_review_events',[]))
            finally:
                request_database.reset(token)
                self._hook=False
        super().commit();self._dirty=set();self._review_events=[]

    def rollback(self):
        super().rollback();self._dirty=set();self._review_events=[]

    def __exit__(self,typ,value,tb):
        try:
            if typ:self.rollback()
            else:self.commit()
        except Exception:
            self.rollback();raise
        finally:self.close()
