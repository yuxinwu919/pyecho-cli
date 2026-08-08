function [mx mxs mxx mxxs mxsxs emittx]=SliceAnalysis (z,x,xs,M,to_sort)
    if to_sort, P=sortrows([z x xs]);  z=P(:,1);x=P(:,2);xs=P(:,3); P=[]; end;
    N=length(x);
    mx(1:N,1)=0;mxs(1:N,1)=0; mxx(1:N,1)=0;mxxs(1:N,1)=0; mxsxs(1:N,1)=0; emittx(1:N,1)=0; 
    m=max([round(M/2) 1]);
    xc=cumsum(x);
    xsc=cumsum(xs);
    for i =1:N,
        n1=max(1,i-m);
        n2=min(N,i+m);
        dq=n2-n1;
        mx(i)=(xc(n2)-xc(n1))/dq;
        mxs(i)=(xsc(n2)-xsc(n1))/dq;
    end;
    x=x-mx; xs=xs-mxs;
    x2c=cumsum(x.*x);xs2c=cumsum(xs.*xs);
    xxsc=cumsum(x.*xs);
    for i =1:N, 
        n1=max(1,i-m);
        n2=min(N,i+m);
        dq=n2-n1;
        mxx(i)=(x2c(n2)-x2c(n1))/dq;
        mxsxs(i)=(xs2c(n2)-xs2c(n1))/dq;
        mxxs(i)=(xxsc(n2)-xxsc(n1))/dq;
    end;
    emittx=sqrt(mxx.*mxsxs-mxxs.*mxxs);
    