#!/usr/bin/env python3
"""Regenerate six grayscale figures from existing release analysis outputs.

No VM, acquisition, network request, or source evidence mutation is performed.
Matplotlib and NumPy are optional dependencies for this figure-only command.
Recompute registered tables and A3/A4 from the raw release records first.
"""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--release-root',type=Path,required=True)
parser.add_argument('--recomputed',type=Path,help='RECOMPUTED_RESULTS.json from analysis/recompute.py; default release derived copy')
parser.add_argument('--a3-a4',type=Path,help='A3_A4_RESULTS.json from analysis/grid_strict_reanalysis.py; default release derived copy')
parser.add_argument('--out',type=Path,default=Path('/tmp/idbv2-rebuilt-figures'),help='Separate derived output folder outside the evidence release')
parser.add_argument('--compare-dir',type=Path,help='Optional existing reference PNG directory; read-only')
args=parser.parse_args()
ROOT=args.release_root.resolve()
OUTPUT=args.out.resolve()
if OUTPUT==ROOT or ROOT in OUTPUT.parents:
    parser.error('--out must be outside the release evidence folder')
if args.compare_dir and args.compare_dir.resolve()==OUTPUT:
    parser.error('--out must differ from the read-only --compare-dir')
RECOMPUTED=(args.recomputed or ROOT/'derived/RECOMPUTED_RESULTS.json').resolve()
A3A4=(args.a3_a4 or ROOT/'derived/a3_a4/A3_A4_RESULTS.json').resolve()
for path in [RECOMPUTED,A3A4]:
    if not path.is_file():parser.error('Missing analysis output: '+str(path))
data=json.loads(RECOMPUTED.read_text())
X=json.loads(A3A4.read_text())
assert len(data['rows'])==930 and len(data['cells'])==95
assert data['eligible']==925 and data['counts']=={'lost':585,'recovered':340,'unknown':4,'no_result':1}
assert len(X['two_second_records'])==20 and sum(t['endpoint']=='recovered' for t in X['two_second_records'])==3
assignments={}
for row in data['rows']:
    a=row['assignment']; key=(a['experiment'],a['condition_id'])
    assignments.setdefault(key,a)
A={'cells':[]}
for c in data['cells']:
    assert c['eligible']==c['recovered']+c['lost']
    A['cells'].append(dict(assignment=assignments[(c['family'],c['condition_id'])],
        recovered=c['recovered'],eligible=c['eligible'],unknown=c['unknown_result'],
        cp=[c['cp95_lower'],c['cp95_upper']]))
families=[('close_aligned_recovery_grid','Close-aligned grid',18,10),('held_connection_recovery_sweep','Held sweep and close controls',7,10),('six_key_conditions','Six key conditions',6,10),('target_byte_diagnostics','Byte capture and forensics',4,10),('trace_category_timelines','Trace-category timelines',4,5),('fault_scope_comparison','Fault scope',12,10),('block_state_recovery','Block state',12,10),('environment_sensitivity','Environment',16,10),('application_and_background_activity','Workload',16,10)]
keys=['immediate_close_late_deadline','delayed_close_short_interval','held_five_seconds','held_fifteen_seconds']
keylabel={keys[0]:'Immediate close; 2.50 s',keys[1]:'Close at 1 s; 2.75 s',keys[2]:'Held 5 s',keys[3]:'Held 15 s'}
def cells(f):return [c for c in A['cells'] if c['assignment']['experiment']==f]
def cell(f,**kw):
    found=[c for c in cells(f) if all(c['assignment'].get(k)==v for k,v in kw.items())]
    assert len(found)==1,(f,kw,len(found))
    return found[0]
OUTPUT.mkdir(parents=True,exist_ok=True)
config=tempfile.TemporaryDirectory(prefix='idbv2-figure-mpl-')
os.environ.setdefault('MPLCONFIGDIR',config.name)
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
except ImportError as e:
    parser.exit(2,'Figure dependencies unavailable: '+str(e)+'\nInstall matplotlib and numpy in your analysis environment; no VM or acquisition is required.\n')
plt.rcdefaults()
plotted_cells=[]
plt.rcParams.update({'font.family':'DejaVu Serif','font.size':10,'axes.labelsize':10,'axes.titlesize':11,'legend.fontsize':9,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':220})
def error(ax,x,c,marker='o',color='black',label=None):
 plotted_cells.append(dict(family=c['assignment']['experiment'],condition_id=c['assignment']['condition_id'],x=float(x),recovered=c['recovered'],eligible=c['eligible'],unknown_result=c['unknown'],cp95=c['cp'],marker=marker,color=color)); y=c['recovered']/c['eligible'];l,h=c['cp'];ax.errorbar(x,y,yerr=[[y-l],[h-y]],fmt=marker,color=color,mfc='white' if marker!='o' else color,ms=6,capsize=3,elinewidth=1.05,label=label,zorder=4)
def axis(ax):ax.set_ylim(-.08,1.13);ax.set_yticks([0,.25,.5,.75,1]);ax.set_yticklabels(['0','25','50','75','100']);ax.grid(axis='y',color='.87',linewidth=.6);ax.set_ylabel('Recovered (%)')
def save(fig,name):fig.savefig(OUTPUT/name,bbox_inches='tight',facecolor='white');plt.close(fig)
# Grid includes an achieved-time scatter, separate from assigned-cell intervals.
fig,axs=plt.subplots(2,1,figsize=(6.5,5.6),gridspec_kw={'height_ratios':[1,1]},sharex=False)
for i,(cl,mark,col) in enumerate([(0,'o','black'),(1000,'s','.45')]):
 for gap in range(1600,2401,100):
  c=cell(families[0][0],close_ms=cl,fault_after_close_ms=gap);error(axs[0],gap/1000+(-.012 if cl==0 else .012),c,mark,col,('Close at 0 s' if cl==0 else 'Close at 1 s') if gap==1600 else None)
  axs[0].text(gap/1000+(-.023 if cl==0 else .023),-.065 if cl==0 else 1.075,str(c['recovered']),ha='center',fontsize=8,color=col)
 axis(axs[0]);axs[0].set_xticks(np.arange(1.6,2.41,.1));axs[0].set_xlabel('Assigned close-to-dispatch gap (s)');axs[0].legend(loc='center left',frameon=True);axs[0].set_title('(a) Cell estimates and exact 95% intervals')
for t in X['two_second_records']:
 cl=t['assigned_close_ms']/1000; recovered=t['endpoint']=='recovered'; y=cl+.2*int(recovered)
 axs[1].errorbar(t['achieved_estimated_gap_s'],y,xerr=t['clock_mapping_uncertainty_ms']/1000,fmt='o' if cl==0 else 's',ms=4,color='black' if recovered else '.5',mfc='black' if recovered else 'white',capsize=2,elinewidth=.75)
axs[1].set_yticks([0,.2,1,1.2]);axs[1].set_yticklabels(['0 s: lost','0 s: recovered','1 s: lost','1 s: recovered']);axs[1].set_ylim(-.16,1.36);axs[1].set_xlim(1.999,2.0103);axs[1].set_xticks([2.000,2.002,2.004,2.006,2.008,2.010]);axs[1].ticklabel_format(axis='x',style='plain',useOffset=False);axs[1].set_xlabel('Achieved estimated close-to-dispatch interval (s)');axs[1].set_title('(b) Assigned 2.0 s trials with mapping half-RTT');axs[1].grid(axis='x',color='.9');fig.tight_layout(pad=1.2);save(fig,'01_grid.png')
fig,ax=plt.subplots(figsize=(6.5,3.55))
for t in [5000,7500,10000,12500,15000]:
 c=cell(families[1][0],held=True,fault_after_ack_ms=t);error(ax,t/1000-.10,c,'o','black','Original connection held' if t==5000 else None);ax.annotate(f"{c['recovered']}/10",(t/1000-.1,c['recovered']/10),xytext=(0,10),textcoords='offset points',ha='center',fontsize=9)
for t in [5000,15000]:
 c=cell(families[1][0],held=False,fault_after_ack_ms=t);error(ax,t/1000+.10,c,'s','.45','Immediate close allowed' if t==5000 else None);ax.annotate('10/10',(t/1000+.1,1),xytext=(0,10),textcoords='offset points',ha='center',fontsize=9)
axis(ax);ax.set_xticks([5,7.5,10,12.5,15]);ax.set_xlabel('Assigned host-ACK-to-dispatch deadline (s)');ax.legend(loc='center',frameon=True);fig.tight_layout();save(fig,'02_held.png')
def grouped(f,dim,alts,labels,name):
 fig,axs=plt.subplots(2,2,figsize=(6.5,5.0))
 for k,ax in zip(keys,axs.flat):
  for i,v in enumerate(alts):
   c=cell(f,key=k,**{dim:v});error(ax,i,c,['o','s','^','D'][i],['black','.35','.6','.15'][i]);ax.text(i,1.075,f"{c['recovered']}/{c['eligible']}"+('*' if c['unknown'] else ''),ha='center',fontsize=9)
  axis(ax);ax.set_title(keylabel[k]);ax.set_xticks(range(len(alts)),labels,fontsize=9);ax.set_xlim(-.45,len(alts)-.55)
 fig.tight_layout(pad=1.0,h_pad=2);save(fig,name)
grouped(families[5][0],'fault',['qmp_reset','sysrq_reboot','browser_sigkill'],['QMP reset','SysRq reboot','SIGKILL'],'03_fault.png')
grouped(families[6][0],'mapper',['linear_control','dm_log_writes','dm_flakey_drop_writes'],['Linear','Log writes','Drop writes'],'04_block.png')
grouped(families[7][0],'environment_profile',['ext4_custom_reference','ext4_defaults_fixed','ext4_defaults_random','xfs_fixed'],['Custom\next4','Default\next4','Random\nuptime','XFS'],'05_environment.png')
grouped(families[8][0],'workload',['single_256_bytes','background_fsync','ten_records_one_transaction','four_connections'],['Quiet','Fsync\nload','10\nrecords','4\nconns'],'06_workload.png')

def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
figure_names=['01_grid.png','02_held.png','03_fault.png','04_block.png','05_environment.png','06_workload.png']
assert len(plotted_cells)==81
figure_data=dict(role='Existing data only; no new scientific units',
    scientific_assignments=930,eligible=925,recovered=340,lost=585,
    original_95_cells_separate=True,new_scientific_units=0,
    sources=dict(recomputed_sha256=sha(RECOMPUTED),a3_a4_sha256=sha(A3A4)),
    plotted_cells=plotted_cells,
    figure1_achieved_two_second_points=X['two_second_records'],
    semantics='Pointwise exact95% recovery intervals. Figure1 two panels separate assigned-cell estimates from20 achieved-time points with mapping half-RTT. Unknowns are not losses; fault held15 SIGKILL uses9 eligible and an asterisk. Display offsets do not change deadlines. No interpolated threshold or pooled rate.')
(OUTPUT/'FIGURE_DATA.json').write_text(json.dumps(figure_data,indent=2)+'\n')
comparisons=[]
for name in figure_names:
    p=OUTPUT/name
    result=dict(name=name,sha256=sha(p),bytes=p.stat().st_size)
    if args.compare_dir:
        ref=args.compare_dir/name
        if not ref.is_file():
            result.update(reference_present=False,comparison='missing_reference')
        else:
            result.update(reference_present=True,reference_sha256=sha(ref),byte_identical=sha(p)==sha(ref))
            from PIL import Image
            with Image.open(p) as generated,Image.open(ref) as original:
                left=np.asarray(generated.convert('RGBA')).astype(np.int16)
                right=np.asarray(original.convert('RGBA')).astype(np.int16)
            result.update(generated_shape=list(left.shape),reference_shape=list(right.shape))
            if left.shape==right.shape:
                delta=np.abs(left-right)
                result.update(pixel_identical=bool(np.array_equal(left,right)),
                    differing_pixels=int(np.count_nonzero(np.any(delta!=0,axis=2))),
                    max_channel_difference=int(delta.max()))
            else:result.update(pixel_identical=False,comparison='different_image_dimensions')
    comparisons.append(result)
report=dict(role='Portable read-only scientific figure reproduction',new_scientific_units=0,
    matplotlib_version=matplotlib.__version__,numpy_version=np.__version__,backend=matplotlib.get_backend(),
    source_records_modified=False,plot_color_scheme='grayscale',
    plotted_cell_estimates=81,figure1_achieved_points=20,
    output=str(OUTPUT),figures=comparisons,
    comparison_limit='Fonts, renderer and library versions can change PNG bytes or pixels; numerical series are separately recorded in FIGURE_DATA.json. Pixel similarity alone does not validate raw inputs.')
(OUTPUT/'FIGURE_REBUILD_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
config.cleanup()
print(json.dumps(report,indent=2))
