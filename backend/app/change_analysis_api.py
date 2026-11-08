from fastapi import APIRouter
from pydantic import BaseModel,ConfigDict,Field
from app.adjustment_api import invoke
from app.services import change_analysis_service as service,timeline_service
from app.workflow_api import actor
router=APIRouter(prefix='/api',tags=['Version comparison, scenarios and historical replay'])
class Selection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version:str='v3'
    scenario_ids:list[str]=Field(default_factory=list,max_length=5)
class Save(Selection):
    id:str|None=None
    note:str=Field(min_length=1,max_length=4000)
    expected_revision:int=Field(ge=0)
class Impact(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version:str='v3'
    refs:list[str]=Field(min_length=1,max_length=100)
    note:str=Field(min_length=1,max_length=4000)

@router.get('/version-comparison')
def compare(before:str='v1',after:str='v3'):return invoke(service.comparison,before,after)
@router.get('/what-if')
def catalog(version:str='v3'):return invoke(service.alternatives,version)
@router.post('/what-if/compare')
def select(payload:Selection):return invoke(service.alternatives,payload.version,payload.scenario_ids)
@router.post('/what-if/analyses')
def save(payload:Save):return invoke(service.save_analysis,actor(),payload.model_dump())
@router.get('/what-if/analyses')
def analyses():return invoke(service.analysis_history,actor())
@router.get('/timeline-replay')
def replay(at:str):return invoke(timeline_service.replay,at)
@router.get('/timeline-replay/evidence')
def evidence(at:str,ref:str,version:str|None=None):
    from app.security_context import request_principal
    from app.services import workflow_service as w
    person=request_principal.get()
    if person:
        with w.connection() as db:
            w.require_access(db,person)
            limited='*' not in w.membership(db,person)['data']['areas']
        if limited:
            context=invoke(timeline_service.HistoricalContext,at)
            node=context.unavailable(ref,version or context.version,'outside_assignment_scope').model_dump()
            node['reason']='Historical evidence requires an entire-engagement assignment. No source value is disclosed.'
            return {'mode':'historical','as_of':context.at.isoformat(),'version':version or context.version,'reference':ref,
                    'resolution':node,'nodes':[node],'unresolved':[node],'document_ids':[],'cycles':[],'changes_current_state':False}
    return invoke(timeline_service.replay_evidence,at,ref,version)
@router.get('/change-impact')
def impact(ref:str='SchC.1',version:str='v3'):return invoke(service.impact_report,[ref],version)
@router.post('/change-impact/reassess')
def reassess(payload:Impact):return invoke(service.record_impact,actor(),payload.model_dump())
