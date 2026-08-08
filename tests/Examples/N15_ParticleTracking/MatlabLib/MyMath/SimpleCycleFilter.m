function y=SimpleCycleFilter(x,p)
n=length(x);
y(1:n,1)=0;
N=2*p+1;
for i=1:n,
    i0=i-p;
    i1=i+p;
    s=0;
    for j=i0:i1,
        ind=j;
        if ind<1, ind=n+j; end;
        if ind>n, ind=ind-n; end;
        s=s+x(ind);
    end;
    y(i)=s/N;
end;
        