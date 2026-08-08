function y=SimpleFilter(x,p,iter)
n=length(x);
if iter==0, y=x; return; end;
for k=1:iter,
    
y(1:n,1)=0;
for i=1:n,
    i0=i-p;
    if i0<1, i0=1; end;
    i1=i+p;
    if i1>n, i1=n; end;
    s=0;
    for j=i0:i1,s=s+x(j);end;
    y(i)=s/(i1-i0+1);
end;
x=y;
end;
        