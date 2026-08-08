clear all;close all;
a=2e-1;h=0.5e-1;p=0.5e-1; g=0.25e-1; %in cm

N=2200 %1m
cond=0;
show_geometry=true;


out(1:4*N+2,1:10)=0;
out(1:4*N+2,10)=cond;


ind=1;
x1=-p; x2=0; y1=a; y2=a;
if show_geometry, line([x1  x2],[y1 y2]); hold on;end;
out(ind,1)=x1;   out(ind,2)=y1;
out(ind,3)=x2;   out(ind,4)=y2;
out(ind,10)=0;
for i=1:N,
    ind=ind+1;
    x1=x2; x2=x1; y1=a; y2=a+h;
    if show_geometry, line([x1  x2],[y1 y2]);end;
    out(ind,1)=x1;   out(ind,2)=y1;    out(ind,3)=x2;   out(ind,4)=y2;
    ind=ind+1;
    x1=x2; x2=x2+g; y1=a+h; y2=y1;
    if show_geometry, line([x1  x2],[y1 y2]);end;
    out(ind,1)=x1;   out(ind,2)=y1;    out(ind,3)=x2;   out(ind,4)=y2;
    ind=ind+1;
    x1=x2; x2=x2; y1=a+h; y2=a;
    if show_geometry, line([x1  x2],[y1 y2]);end;
    out(ind,1)=x1;   out(ind,2)=y1;    out(ind,3)=x2;   out(ind,4)=y2;
    ind=ind+1;
    x1=x2; x2=x2+p-g; y1=a; y2=y1;
    if show_geometry, line([x1  x2],[y1 y2]);end;
    out(ind,1)=x1;   out(ind,2)=y1;    out(ind,3)=x2;   out(ind,4)=y2;
end;    

ind=ind+1;
x1=x2; x2=x2+p; y1=a; y2=y1;
if show_geometry, line([x1  x2],[y1 y2]);end;
out(ind,1)=x1;   out(ind,2)=y1;    out(ind,3)=x2;   out(ind,4)=y2;
out(ind,10)=0;
if show_geometry, xlim([-0.1,0.26]);ylim([-0.1,0.26]); end;
save SLAC_2mm_1m10.txt ind out -ascii